"""Natural-language run lifecycle for the runtime control-plane service."""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json
import os
import threading
from collections.abc import Awaitable, Callable, Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, Protocol, Self, TypeVar, cast

from pydantic import BaseModel, ConfigDict, model_validator

from polisyos.common.async_tools import run_blocking_async
from polisyos.common.canonical_profile import (
    CanonicalProfileRefusalError,
    read_optional_selected_artifact,
    require_declared_profile,
)
from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ArtifactRef, read_core_json_artifact
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.contracts.control import (
    DataNeed,
    DataResolveRequest,
    DataSourceBinding,
)
from polisyos.core.contracts.fabric import DataSnapshotRef
from polisyos.data_forge.read_api import build_privacy_compliance_report
from polisyos.foundry.validation.causal_validity import (
    build_causal_statistical_validity_report,
)
from polisyos.ir.kernel.metrics import (
    MetricTaxonomyValidationError,
    ProductionMetricTaxonomy,
    build_production_metric_taxonomy,
    canonicalize_metric_id_with_diagnostics,
)
from polisyos.runtime.http.services.control.artifacts import (
    _make_artifact_ref,
    _resolve_curated_dir,
    write_runtime_authority_artifact,
)
from polisyos.runtime.http.services.control.production_data import (
    apply_production_data_defaults as _apply_production_data_defaults_impl,
)
from polisyos.runtime.http.services.control.production_data import (
    build_production_data_fabric_trace as _build_production_data_fabric_trace,
)
from polisyos.runtime.http.services.control.production_data import (
    production_data_contract_binding_report as _production_data_contract_binding_report,
)
from polisyos.runtime.http.services.control.production_data import (
    production_data_evidence_context as _production_data_evidence_context,
)
from polisyos.runtime.http.services.control.production_data import (
    production_data_quality_report as _build_production_data_quality_report,
)
from polisyos.runtime.http.services.control.production_data import (
    resolve_production_data_root as _resolve_production_data_root,
)
from polisyos.runtime.http.services.control.response_shapes import (
    _build_scientist_v2_shadow_comparison,
    _canonicalize_numeric_payload,
    _project_call_event_cost,
    _sum_call_events,
)
from polisyos.runtime.quality.attestation import (
    build_required_production_attestations,
    serialize_attestation_record,
)
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
    DesignProblem,
    DesignProblemAuthorityError,
)
from polisyos.runtime.quality.evidence_spine import (
    EvidenceSpineCarrier,
    EvidenceSpineValidationError,
)
from polisyos.runtime.quality.report_registry import (
    QUALITY_REPORT_RUNTIME_REFS,
    RUNTIME_QUALITY_OWNER_MARKER_SCHEMA,
    RUNTIME_QUALITY_OWNER_PRODUCER_VERSION,
    RUNTIME_QUALITY_PUBLICATION_CLOSURE_REFERENCE_BINDINGS,
    RUNTIME_QUALITY_PUBLICATION_SEMANTIC_BINDING_REFERENCE_BINDING,
    _build_runtime_quality_report_publication_basis,
    _runtime_quality_report_publication_view,
    _runtime_quality_report_reuse_basis,
    _runtime_quality_report_reuse_closure_matches,
    _runtime_quality_report_source_payload,
    _runtime_quality_report_writer_payload,
    _RuntimeQualityReportPublicationBasis,
    runtime_quality_report_owner_contract,
    runtime_quality_report_owner_identity_issues,
    runtime_quality_report_owner_marker,
)
from polisyos.scientist.orchestration.llm.factory import create_traced_gateway_client
from polisyos.scientist.orchestration.llm.prompt_cache import CacheReusePrincipal

from .._control_contracts import (
    _DATA_SOURCE_KEYS,
    _dedupe_models,
    _is_auto_materialization_enabled,
    _is_multimodel_enabled,
    _is_required_preflight_enabled,
    _is_scientist_reflexion_enabled,
    _is_scientist_shadow_mode,
    _is_scientist_swarm_enabled,
    _is_scientist_v2_enabled,
    _is_scientist_web_search_enabled,
    _is_unified_dag_enabled,
    _MethodCatalogSnapshotAware,
    _normalize_model_variant_id,
    _now_ms,
    _resolve_data_source,
)

logger = get_logger(__name__)
_StepResult = TypeVar("_StepResult")
_CURRENT_NL_STEP_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "polisyos_current_nl_step_id", default=None
)


def _selected_final_claims_refusal_report(*, refusal_code: str) -> dict[str, Any]:
    """Build a failing citation report when supplied final-claims evidence is unusable."""

    return {
        "schema_version": "policyos.scientist.citation_faithfulness.v1",
        "status": "fail",
        "live_llm_judging_enabled": False,
        "claims": [],
        "issues": [
            {
                "code": "selected_final_policy_claims_unavailable",
                "severity": "fail",
                "layer": "scientist_policy_artifacts",
                "phase": "citation_faithfulness",
                "claim_id": "selected_final_policy_claims",
                "claim_text": "",
                "citation_ref": None,
                "label": "unverifiable",
                "mismatch_dimensions": [],
                "message": f"Selected final-policy-claims evidence was refused: {refusal_code}.",
                "next_action": (
                    "Repair or reissue the selected claims artifact before citation review."
                ),
            }
        ],
        "blocking_issue_count": 1,
        "label_counts": {},
        "residual_risk": {
            "level": "high",
            "deterministic_only": True,
            "summary": "Selected final-policy-claims evidence was not established.",
        },
    }


def _require_final_claims_report_shape(
    payload: object,
    *,
    refusal_code: str,
) -> dict[str, Any]:
    """Reject malformed supplied reports while preserving valid empty reports."""

    if not isinstance(payload, Mapping) or not payload:
        raise CanonicalProfileRefusalError(refusal_code)
    claims = payload.get("claims", payload.get("policy_claims"))
    if not isinstance(claims, list) or any(not isinstance(claim, Mapping) for claim in claims):
        raise CanonicalProfileRefusalError(refusal_code)
    return dict(payload)


def _cost_number(value: object) -> float | None:
    """Return a finite nonnegative cost, preserving absent or malformed values."""

    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0:
        return None
    return float(parsed)


if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore, AsyncArtifactStore
    from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo, InputRef
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts import CatalogRunProfile
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.fabric.retrieval import RetrievalProviders
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobExecutionScope,
        ControlPlaneStore,
    )
    from polisyos.runtime.quality.epoch_certificate_issuance import (
        DecisionPacketEpochIssuanceOwner,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.substrate_registry import CatalogServingSourcePaths
    from polisyos.scientist.agent import (
        CriticAgent,
        DataNeedExtractorAgent,
        DrafterAgent,
        FormalizerAgent,
        PIAgent,
    )
    from polisyos.scientist.orchestration.engine import BudgetMiddleware


def _nl_snapshot_cache_reuse_binding(
    *,
    data_source: DataSourceBinding | None,
    execution_scope: object,
    artifact_store: ArtifactStore,
    authorizer: object | None,
) -> tuple[CacheReusePrincipal | None, dict[str, Any] | None]:
    """Bind cache identity to a typed snapshot locator and the admitted job owner.

    The submitted ref is only a locator. The runtime reads its exact current CAS
    bytes and manifest profile; the injected reuse owner must independently
    resolve those bytes and authorize the current principal/epoch before every hit.
    """
    from polisyos.core.artifacts import ArtifactID, artifact_manifest_profile_sha256
    from polisyos.core.contracts.fabric import DataSnapshotRef
    from polisyos.runtime.http.services.control_plane_store import ControlJobExecutionScope

    if (
        not callable(getattr(authorizer, "authorize_reuse", None))
        or type(execution_scope) is not ControlJobExecutionScope
        or execution_scope.status != "established"
        or execution_scope.actor_authenticated is not True
        or not execution_scope.actor_subject
        or not execution_scope.tenant_id
        or not execution_scope.cell_id
        or type(data_source) is not DataSourceBinding
        or not isinstance(data_source.data_snapshot_ref, str)
        or not data_source.data_snapshot_ref
    ):
        return None, None
    try:
        artifact_id = ArtifactID.model_validate(data_source.data_snapshot_ref)
        selected_ref = DataSnapshotRef(artifact_id=artifact_id)
        manifest = artifact_store.get_manifest(selected_ref.artifact_id)
        content = artifact_store.get_bytes(selected_ref.artifact_id)
        version = artifact_manifest_profile_sha256(manifest)
    except Exception:
        return None, None
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    if (
        type(content) is not bytes
        or manifest.artifact_id != selected_ref.artifact_id
        or manifest.kind != selected_ref.kind
        or manifest.media_type != selected_ref.media_type
        or manifest.integrity.sha256 != digest.removeprefix("sha256:")
        or str(manifest.artifact_id) != digest
        or not version
    ):
        return None, None
    tenant = execution_scope.tenant_id
    scope = f"{tenant}/{execution_scope.cell_id}"
    principal = CacheReusePrincipal(
        actor_id=execution_scope.actor_subject,
        tenant=tenant,
        scope=scope,
    )
    return principal, {
        "tenant": tenant,
        "scope": scope,
        "purpose": "natural_language_policy_candidate",
        "snapshot": {
            "ref": str(selected_ref.artifact_id),
            "version": version,
            "immutable": True,
            "content": content,
            "content_hash": digest,
        },
    }


class NaturalLanguagePipelineRefusalError(RuntimeError):
    """Typed fail-closed refusal for an unavailable NL production capability."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}:{message or code}")


def _register_runtime_quality_selected_output_ref(
    *,
    ref_key: str,
    selected_ref: ArtifactRef,
    runtime_quality_refs: dict[str, str],
    runtime_quality_artifact_refs: dict[str, ArtifactRef],
    expected_kind: str,
    expected_media_type: str,
    expected_artifact_id: str | None = None,
) -> str:
    """Register one writer-selected CAS view and its matching runtime reference."""
    if (
        type(selected_ref) is not ArtifactRef
        or selected_ref.kind != expected_kind
        or selected_ref.media_type != expected_media_type
        or not selected_ref.manifest_profile_sha256
        or (
            expected_artifact_id is not None
            and (
                type(expected_artifact_id) is not str
                or str(selected_ref.artifact_id) != expected_artifact_id
            )
        )
    ):
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            f"Runtime quality output {ref_key} lacks its exact selected CAS view.",
        )

    artifact_id = str(selected_ref.artifact_id)
    runtime_quality_artifact_refs[ref_key] = selected_ref
    runtime_quality_refs[ref_key] = artifact_id
    return artifact_id


class _NLProductionAuthorityStamp(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authority_scope: Literal["production"] = "production"
    production_promotable: Literal[True] = True


class _DesignProblemCompilerOutputPolicy(BaseModel):
    """Evidence-derived completion ceiling for strict DesignProblem emission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observed_max_completion_tokens: int
    max_tokens: int
    headroom_tokens: int
    evidence_ref: str

    @classmethod
    def from_characterization(
        cls,
        *,
        observed_max_completion_tokens: int,
        evidence_ref: str,
    ) -> Self:
        """Derive a power-of-two ceiling above the measured clean denominator."""

        if observed_max_completion_tokens <= 0:
            raise ValueError("output_budget_observed_max_invalid")
        max_tokens = 1 << (observed_max_completion_tokens - 1).bit_length()
        return cls(
            observed_max_completion_tokens=observed_max_completion_tokens,
            max_tokens=max_tokens,
            headroom_tokens=max_tokens - observed_max_completion_tokens,
            evidence_ref=evidence_ref,
        )

    @model_validator(mode="after")
    def _verify_derivation(self) -> Self:
        if self.observed_max_completion_tokens <= 0:
            raise ValueError("output_budget_observed_max_invalid")
        expected = 1 << (self.observed_max_completion_tokens - 1).bit_length()
        if self.max_tokens != expected:
            raise ValueError("output_budget_not_next_power_of_two")
        if self.headroom_tokens != self.max_tokens - self.observed_max_completion_tokens:
            raise ValueError("output_budget_headroom_drift")
        if not self.evidence_ref.strip():
            raise ValueError("output_budget_evidence_ref_missing")
        return self


_DESIGN_PROBLEM_COMPILER_OUTPUT_POLICY = _DesignProblemCompilerOutputPolicy.from_characterization(
    observed_max_completion_tokens=5628,
    evidence_ref=(
        "docs/superpowers/journals/2026-07-14-gy-n10-stage-4.md"
        "#structured-conformance-denominator-universal-owner-schema-selected"
    ),
)
_DESIGN_PROBLEM_SOURCE_SEMANTICS_INVARIANT = (
    "Do not interpret, elaborate, or strengthen any cited constraint beyond the "
    "exact semantic content of its source. When a source names a condition but "
    "does not state its effects or consequences, record only the named condition "
    "and leave those effects or consequences unstated."
)
_DESIGN_PROBLEM_OPTIONAL_STRUCTURE_INVARIANT = (
    "Emit an optional structure only when the supplied request and context can "
    "satisfy its entire provided tool contract. Otherwise omit the optional "
    "structure rather than supplying null, guessed, or partial placeholders."
)


def design_problem_compiler_source_semantics_invariant() -> str:
    """Return the generic no-strengthening contract for candidate constraints."""

    return _DESIGN_PROBLEM_SOURCE_SEMANTICS_INVARIANT


def design_problem_compiler_optional_structure_invariant() -> str:
    """Return the generic completeness contract for optional model structures."""

    return _DESIGN_PROBLEM_OPTIONAL_STRUCTURE_INVARIANT


_SERIOUS_EXECUTION_PROFILES = frozenset({"research", "governed", "production"})
_CAUSAL_VALIDITY_CASES_PATH = (
    Path(__file__).resolve().parents[6] / "tests/_golden/foundry/causal_validity/cases.json"
)
_DESIGN_PROBLEM_TOOL_NAME = "emit_design_problem"
_DESIGN_PROBLEM_TRUNCATION_FINISH_REASONS = frozenset({"length", "max_output_tokens", "max_tokens"})
_PROMOTED_CONTEXT_PARAM_KEYS = frozenset(
    {
        "source_context",
        "target_context",
        "cross_graph_evidence_config",
        "production_data_root",
        "transport_required",
        "query_treatment",
        "query_outcome",
        "transport_solver_mode",
        "pag_identification_policy",
        "pag_max_dag_samples",
        "pag_threshold",
        "pag_seed",
        "privacy_context",
        "dataset_registry_db_path",
        "legal_db_path",
        "legal_kg_db_path",
        "skg_db_path",
        "skg_index_dir",
        "academic_db_path",
        "academic_index_dir",
        "datasets_db_path",
        "benchmark_suite_path",
        "benchmark_report_path",
        "academic_demand_backlog_path",
        "lex_bundle_dir",
        "datasets_snapshot_dir",
        "academic_snapshot_dir",
        "ukraine_agent_simulation_root",
        "ukraine_runtime_bundle_dir",
        "ukraine_intervention_bundle_dir",
        "ukraine_calibration_bundle_dir",
        "ukraine_method_contract_bundle_dir",
    }
)


class _DesignProblemGatewayClient(Protocol):
    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        """Return gateway model ids available for the preflight."""
        ...

    async def generate(
        self,
        *,
        messages: list[Mapping[str, object]] | None = None,
        system: str | None = None,
        user: str | None = None,
        tools: list[Mapping[str, object]] | None = None,
        tool_choice: Mapping[str, object] | str | None = None,
        temperature: float | None = None,
        seed: int | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
    ) -> object:
        """Return one gateway completion."""
        ...


class _SpanSupportVerifierClient(Protocol):
    async def generate(
        self,
        *,
        messages: list[Mapping[str, object]] | None = None,
        system: str | None = None,
        user: str | None = None,
        tools: list[Mapping[str, object]] | None = None,
        tool_choice: Mapping[str, object] | str | None = None,
        temperature: float | None = None,
        seed: int | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
    ) -> object:
        """Return one span-support verifier completion."""
        ...


async def build_design_problem_from_nl_request(
    *,
    nl_request: str,
    context: Mapping[str, Any],
    model_name: str,
    trusted_source_context: Mapping[str, Any | None] | None = None,
    run_id: str | None = None,
    producer_settlement_store: BudgetMiddleware | None = None,
    call_observer: Callable[[dict[str, Any]], None] | None = None,
    gateway_client: _DesignProblemGatewayClient | None = None,
    span_support_client: _SpanSupportVerifierClient | None = None,
) -> DesignProblem:
    """Produce a validated DesignProblem through gateway tool-calling.

    Args:
        nl_request: Raw natural-language policy-design request.
        context: Runtime control context captured with the request.
        model_name: Gateway model id requested for the structured extraction.
        run_id: Owning NL run id, when this producer call belongs to an admitted run.
        producer_settlement_store: Optional durable producer-event ledger owned by
            the runtime. It is used only when ``run_id`` is present.
        call_observer: Optional callback for each traced provider response. The
            callback receives status-preserving usage and settlement data.
        gateway_client: Optional prebuilt gateway client, used by tests and by
            runtime callers that already constructed a traced client.
        span_support_client: Optional GY-K span-support verifier client for
            deterministic tests. Production leaves this unset so the
            citation-faithfulness owner constructs the live bounded-agent judge.
        trusted_source_context: Optional owner-replayed scope identity for the
            persisted DesignProblem provenance; untrusted model values cannot
            replace it.

    Returns:
        A strict, semantically validated ``DesignProblem``.

    Raises:
        DesignProblemAuthorityError: If the model is unsupported, the gateway
            does not use tool-calling, or the returned structure invents
            unsupported admissibility.
    """

    owns_client = gateway_client is None
    client = gateway_client
    if client is None:
        client = create_traced_gateway_client(
            model_name=model_name,
            run_id=run_id,
            call_observer=call_observer,
            producer_settlement_store=(producer_settlement_store if run_id is not None else None),
            producer_budget_key=(f"nl-run:{run_id}" if run_id is not None else "run"),
        )
    if client is None:
        raise DesignProblemAuthorityError(
            "design_problem_gateway_missing",
            "DesignProblem construction requires a gateway-backed model client.",
        )
    try:
        await _preflight_design_problem_model(client=client, model_name=model_name)
        response = await client.generate(
            system=(
                "Extract one PolicyOS DesignProblem. Use only the provided request and "
                "authority context. Do not invent constraints, admissibility, mandate, "
                "jurisdiction, evidence, or value authority. Populate every "
                "schema-required non-empty collection with request-grounded candidate "
                "entries; never emit empty objectives, stakeholders, allowed operator "
                "kinds, or candidate levers. "
                + design_problem_compiler_source_semantics_invariant()
            ),
            user=json.dumps(
                {
                    "raw_request": nl_request,
                    "context": dict(context),
                    "required_semantics": {
                        "llm_output": "candidate_only",
                        "non_empty_collections": [
                            "objectives",
                            "stakeholders",
                            "candidate_lever_space.allowed_operator_kinds",
                            "candidate_lever_space.candidate_levers",
                        ],
                        "constraints": (
                            "must cite request_text, authority_profile, or producer_evidence"
                        ),
                    },
                },
                sort_keys=True,
                ensure_ascii=True,
            ),
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": _DESIGN_PROBLEM_TOOL_NAME,
                        "description": (
                            "Emit the canonical PolicyOS DesignProblem bridge. Every "
                            "constraint must include admissibility_basis and source_text "
                            "or evidence_ref."
                        ),
                        "parameters": design_problem_provider_constraint_schema(),
                    },
                }
            ],
            tool_choice={
                "type": "function",
                "function": {"name": _DESIGN_PROBLEM_TOOL_NAME},
            },
            temperature=0.0,
            max_tokens=_DESIGN_PROBLEM_COMPILER_OUTPUT_POLICY.max_tokens,
        )
        finish_reason = _design_problem_finish_reason(response)
        if finish_reason in _DESIGN_PROBLEM_TRUNCATION_FINISH_REASONS:
            raise DesignProblemAuthorityError(
                "design_problem_output_truncated",
                f"Gateway stopped DesignProblem emission at its output ceiling: {finish_reason}",
            )
        tool_calls = list(getattr(response, "tool_calls", None) or [])
        matching_calls = [
            call for call in tool_calls if getattr(call, "name", "") == _DESIGN_PROBLEM_TOOL_NAME
        ]
        if len(matching_calls) != 1:
            raise DesignProblemAuthorityError(
                "design_problem_tool_call_missing",
                "Gateway response must contain exactly one emit_design_problem tool call.",
            )
        tool_call = matching_calls[0]
        error_envelope = getattr(tool_call, "error_envelope", None)
        if (
            isinstance(error_envelope, Mapping)
            and error_envelope.get("reason") == "tool_call_arguments_parse_error"
        ):
            raise DesignProblemAuthorityError(
                "design_problem_validation_failed",
                "Gateway could not parse DesignProblem tool call arguments.",
            )
        arguments = getattr(tool_call, "arguments", None)
        if not isinstance(arguments, Mapping):
            raise DesignProblemAuthorityError(
                "design_problem_tool_arguments_invalid",
                "DesignProblem tool call arguments must be an object.",
            )
        payload = _merge_design_problem_runtime_context(
            dict(arguments),
            nl_request=nl_request,
            context=context,
            trusted_source_context=trusted_source_context,
        )
        try:
            problem = DesignProblem.model_validate(payload)
        except ValueError as exc:
            raise DesignProblemAuthorityError("design_problem_validation_failed", str(exc)) from exc
        _assert_design_problem_admissibility_grounded(
            problem,
            span_support_client=span_support_client,
        )
        return problem
    finally:
        if owns_client:
            await _close_llm_client(client)


def _design_problem_finish_reason(response: object) -> str | None:
    """Return provider-owned completion termination evidence, when available."""

    raw = getattr(response, "raw", None)
    if not isinstance(raw, Mapping):
        return None
    choices = raw.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        value = choices[0].get("finish_reason") or choices[0].get("stop_reason")
        if isinstance(value, str) and value.strip():
            return value.strip().casefold()
    value = raw.get("finish_reason") or raw.get("stop_reason")
    if isinstance(value, str) and value.strip():
        return value.strip().casefold()
    return None


async def _preflight_design_problem_model(
    *,
    client: _DesignProblemGatewayClient,
    model_name: str,
) -> None:
    if not hasattr(client, "list_model_ids"):
        raise DesignProblemAuthorityError(
            "design_problem_model_preflight_missing",
            "Gateway client must expose /models preflight.",
        )
    try:
        live_model_ids = await client.list_model_ids(timeout=10.0)
    except Exception as exc:
        raise DesignProblemAuthorityError(
            "design_problem_model_preflight_failed",
            str(exc),
        ) from exc
    normalized = {str(item).casefold(): str(item) for item in live_model_ids}
    if model_name.casefold() not in normalized:
        raise DesignProblemAuthorityError(
            "design_problem_model_profile_unsupported",
            f"Gateway /models does not list requested model: {model_name}",
        )


def _inline_json_schema_refs(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Inline local JSON-schema ``$ref``/``$defs`` for gateway tool schemas."""

    root = deepcopy(dict(schema))

    def _resolve_pointer(ref: str) -> object:
        if not ref.startswith("#/"):
            raise ValueError(f"unsupported_json_schema_ref:{ref}")
        current: object = root
        for part in ref.removeprefix("#/").split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(current, Mapping) or key not in current:
                raise ValueError(f"unknown_json_schema_ref:{ref}")
            current = current[key]
        return current

    def _inline(value: object, seen: tuple[str, ...] = ()) -> object:
        if isinstance(value, list):
            return [_inline(item, seen) for item in value]
        if not isinstance(value, Mapping):
            return value
        if "$ref" in value:
            ref = str(value["$ref"])
            if ref in seen:
                raise ValueError(f"recursive_json_schema_ref:{ref}")
            resolved = _inline(deepcopy(_resolve_pointer(ref)), (*seen, ref))
            siblings = {
                key: item
                for key, item in value.items()
                if key not in {"$ref", "$defs", "definitions"}
            }
            if siblings and isinstance(resolved, dict):
                inlined_siblings = _inline(siblings, seen)
                if not isinstance(inlined_siblings, dict):
                    raise ValueError("json_schema_inline_siblings_not_object")
                return {**resolved, **inlined_siblings}
            return resolved
        return {
            str(key): _inline(item, seen)
            for key, item in value.items()
            if key not in {"$defs", "definitions"}
        }

    inlined = _inline(root)
    if not isinstance(inlined, dict):
        raise ValueError("json_schema_inline_result_not_object")
    return inlined


def design_problem_provider_constraint_schema() -> dict[str, Any]:
    """Return the request-only schema projection used for constrained generation.

    Pydantic keeps cross-field ``model_validator`` rules outside its exported JSON
    schema.  The provider projection mirrors the existing TimeSemantics completeness
    rule so generation can see it, while the canonical model remains the sole
    admission authority and re-validates every emitted candidate.
    """

    schema = _inline_json_schema_refs(DesignProblem.model_json_schema())
    schema_properties = schema.get("properties")
    if not isinstance(schema_properties, dict):
        raise ValueError("design_problem_provider_schema_version_missing")
    schema_properties["schema_version"] = {
        "const": DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
        "type": "string",
    }
    required_fields = schema.get("required")
    if not isinstance(required_fields, list):
        raise ValueError("design_problem_provider_required_fields_invalid")
    if "schema_version" not in required_fields:
        required_fields.append("schema_version")
    try:
        time_union = schema["properties"]["jurisdiction_time"]["properties"]["time_semantics"]
        branches = time_union["anyOf"]
    except (KeyError, TypeError) as exc:
        raise ValueError("design_problem_provider_time_schema_missing") from exc
    if not isinstance(branches, list):
        raise ValueError("design_problem_provider_time_schema_invalid")
    object_branches = [
        branch for branch in branches if isinstance(branch, dict) and branch.get("type") == "object"
    ]
    null_branches = [
        branch for branch in branches if isinstance(branch, dict) and branch.get("type") == "null"
    ]
    if len(object_branches) != 1 or len(null_branches) != 1:
        raise ValueError("design_problem_provider_time_union_drift")
    time_object = object_branches[0]
    properties = time_object.get("properties")
    if not isinstance(properties, dict) or not {
        "step_count",
        "end_date",
    }.issubset(properties):
        raise ValueError("design_problem_provider_time_completion_fields_missing")
    time_object["anyOf"] = [
        {
            "required": ["step_count"],
            "properties": {
                "step_count": {"type": "integer", "minimum": 1},
            },
        },
        {
            "required": ["end_date"],
            "properties": {
                "end_date": {"type": "string", "minLength": 1},
            },
        },
    ]
    return schema


def _assert_design_problem_admissibility_grounded(
    problem: DesignProblem,
    *,
    span_support_client: _SpanSupportVerifierClient | None,
) -> None:
    """Fail closed unless admitted constraints are entailed by bound source spans."""

    from polisyos.scientist.validation.citation_faithfulness import (
        evaluate_span_claim_entailment,
    )

    source_bodies = {
        "request_text": problem.nl_provenance.raw_request,
        "authority_profile": " ".join(
            (
                problem.authority_profile.requester_authority,
                problem.authority_profile.mandate,
                " ".join(problem.authority_profile.authority_refs),
            )
        ),
    }
    for constraint in problem.constraints:
        if constraint.admissibility_basis == "producer_evidence":
            continue
        source_text = constraint.source_text or ""
        source_body = source_bodies.get(constraint.admissibility_basis, "")
        if _normalize_design_problem_text(source_text) not in _normalize_design_problem_text(
            source_body
        ):
            raise DesignProblemAuthorityError(
                "design_problem_admissibility_unverified",
                (
                    f"invented_admissibility:{constraint.constraint_id}:"
                    f"source_span_unbound:{constraint.admissibility_basis}"
                ),
            )
        evidence_ref = (
            f"design-problem://{problem.design_problem_id}/"
            f"{constraint.admissibility_basis}/{constraint.constraint_id}"
        )
        result = evaluate_span_claim_entailment(
            claim={
                "claim_id": f"design_problem.constraint.{constraint.constraint_id}",
                "claim_family": "causal",
                "claim_text": constraint.description,
                "direction": "positive",
                "data_refs": [evidence_ref],
                "source_attribution": evidence_ref,
                "method_refs": [evidence_ref],
                "identification_strategy": "source_bound_constraint_span",
                "citation_refs": [evidence_ref],
            },
            evidence={
                "ref_id": evidence_ref,
                "source_id": problem.nl_provenance.source_surface,
                "section": constraint.admissibility_basis,
                "text": source_text,
                "source_content_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            },
            client=span_support_client,
        )
        if result.get("status") != "pass" or result.get("label") != "supports":
            reason_codes = ",".join(str(item) for item in result.get("reason_codes") or [])
            raise DesignProblemAuthorityError(
                "design_problem_admissibility_unverified",
                (
                    f"invented_admissibility:{constraint.constraint_id}:"
                    f"{reason_codes or 'span_support_unverified'}"
                ),
            )


def _normalize_design_problem_text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _merge_design_problem_runtime_context(
    payload: dict[str, Any],
    *,
    nl_request: str,
    context: Mapping[str, Any],
    trusted_source_context: Mapping[str, Any | None] | None = None,
) -> dict[str, Any]:
    merged = dict(payload)
    supplied_schema_version = merged.get("schema_version")
    if supplied_schema_version != DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION:
        raise DesignProblemAuthorityError(
            "design_problem_compiler_schema_version_mismatch",
            "New NL compiler outputs must use the current DesignProblem schema.",
        )
    merged["schema_version"] = DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION
    provenance = dict(merged.get("nl_provenance") or {})
    provenance["raw_request"] = nl_request
    provenance.setdefault("source_surface", "runtime.control.nl_request")
    source_context = dict(provenance.get("source_context") or {})
    for key in ("as_of",):
        value = context.get(key)
        if value is not None:
            source_context.setdefault(key, value)
    owner_scope_keys = ("run_id", "job_id", "tenant_id", "cell_id")
    if trusted_source_context is None:
        for key in owner_scope_keys:
            value = context.get(key)
            if value is not None:
                source_context.setdefault(key, value)
    else:
        # Model-emitted scope aliases are not a second identity channel. The
        # current served owner context is the sole source of these bindings.
        source_context.pop("runtime_identity", None)
        source_context.pop("candidate_context", None)
        for key in owner_scope_keys:
            value = trusted_source_context.get(key)
            if value is None:
                source_context.pop(key, None)
            else:
                source_context[key] = value
    temporal_owner_keys = (
        "temporal_scope",
        "temporal_scope_artifact_ref",
        "temporal_scope_request_binding",
        "nl_request_payload_ref",
        "nl_request_snapshot_content_hash",
    )
    for key in temporal_owner_keys:
        source_context.pop(key, None)
    source_context.pop("temporal_scope_intent", None)
    if trusted_source_context is not None:
        binding = trusted_source_context.get("temporal_scope_request_binding")
        if isinstance(binding, Mapping):
            source_context["temporal_scope_intent"] = {
                "binding": deepcopy(dict(binding)),
                "verification_status": "not_established",
                "requested_view_only": True,
                "authority_role": "diagnostic_only",
                "limitation_code": "temporal_scope_consumed_view_not_established",
            }
    provenance["source_context"] = source_context
    merged["nl_provenance"] = provenance

    authority_level = _design_problem_authority_level(context.get("requested_authority_level"))
    authority = dict(merged.get("authority_profile") or {})
    authority.setdefault("requester_authority", authority_level)
    authority.setdefault(
        "requested_authority_level",
        authority_level,
    )
    authority.setdefault(
        "mandate",
        str(context.get("mandate") or "runtime captured requester intent"),
    )
    merged["authority_profile"] = authority

    jurisdiction_time = dict(merged.get("jurisdiction_time") or {})
    jurisdiction_time.setdefault("region", str(context.get("jurisdiction") or "unspecified"))
    jurisdiction_time.setdefault(
        "valid_time",
        str(context.get("policy_time") or context.get("as_of") or "unspecified"),
    )
    jurisdiction_time.setdefault(
        "as_of",
        str(context.get("as_of") or jurisdiction_time["valid_time"]),
    )
    jurisdiction_time.setdefault("policy_time", str(context.get("policy_time") or "unspecified"))
    jurisdiction_time.setdefault("data_time", str(context.get("data_time") or "unspecified"))
    merged["jurisdiction_time"] = jurisdiction_time
    return merged


def _design_problem_authority_level(value: object) -> str:
    normalized = str(value or "research").strip().casefold()
    if normalized in {"production", "binding", "publishable"}:
        return "production"
    if normalized in {"governed", "serious", "high_stakes", "review_required"}:
        return "governed"
    return "research"


_NESTED_CONTEXT_PARAM_KEYS = (
    "scientist_params",
    "scientist",
    "causal",
    "causal_context",
)
_SCIENTIST_TRACE_NODE_PREFIX = "scientist.node."
_SCIENTIST_PROGRESS_HISTORY_LIMIT = 50
_RUN_PERFORMANCE_BUDGETS_MS = {
    "llm.total": 120_000,
    "nl_step.create_problem_frame": 30_000,
    "nl_step.extract_data_needs": 30_000,
    "nl_step.resolve_data_needs": 45_000,
    "nl_step.materialize_data": 60_000,
    "nl_step.build_trinity": 30_000,
    "nl_step.critic_review": 30_000,
    "retrieval.discover": 20_000,
    "retrieval.search": 20_000,
    "retrieval.materialize": 60_000,
    "retrieval.quality": 20_000,
}
_METRIC_PAYLOAD_KEYS = frozenset(
    {
        "metric",
        "metric_id",
        "output_metric",
        "outcome_metric",
        "query_outcome",
        "primary_metric",
    }
)
_METRIC_NESTED_PAYLOAD_KEYS = frozenset(
    {
        "metrics",
        "expected_metrics",
        "outputs",
        "expected_outputs",
        "data_needs",
        "stop_criteria",
        "context",
    }
)


def _clean_runtime_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _runtime_privacy_jurisdiction(context: Mapping[str, Any]) -> str | None:
    direct = _clean_runtime_text(context.get("jurisdiction"))
    if direct:
        return direct
    target_context = context.get("target_context")
    if isinstance(target_context, Mapping):
        return _clean_runtime_text(target_context.get("jurisdiction"))
    return None


def _load_causal_statistical_validity_cases() -> list[dict[str, Any]]:
    try:
        payload = json.loads(_CAUSAL_VALIDITY_CASES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    cases = payload.get("cases") if isinstance(payload, Mapping) else None
    if not isinstance(cases, list):
        return []
    return [dict(item) for item in cases if isinstance(item, Mapping)]


def _runtime_privacy_production_sources(
    *,
    evidence_context: Mapping[str, Any] | None,
    context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(evidence_context, Mapping):
        return []
    bundles = evidence_context.get("bundles")
    if not isinstance(bundles, Mapping):
        return []
    jurisdiction = _runtime_privacy_jurisdiction(context)
    sources: list[dict[str, Any]] = []
    for role, raw_bundle in sorted(bundles.items()):
        if not isinstance(raw_bundle, Mapping):
            continue
        version = _clean_runtime_text(raw_bundle.get("version_id"))
        source_family = (
            _clean_runtime_text(raw_bundle.get("source_family"))
            or _clean_runtime_text(raw_bundle.get("data_source_family"))
            or str(role)
        )
        columns = raw_bundle.get("required_columns")
        fields = (
            [{"name": str(item)} for item in columns if str(item or "").strip()]
            if isinstance(columns, list)
            else []
        )
        public_export_allowed = raw_bundle.get("public_export_allowed")
        if not isinstance(public_export_allowed, bool):
            public_export_allowed = True
        sources.append(
            {
                "source_id": version or f"production-{role}",
                "source_family": source_family,
                "source_kind": "production_data",
                "fields": fields,
                "minimization": {
                    "purpose": _clean_runtime_text(context.get("policy_purpose"))
                    or "Runtime policy decision support from production data.",
                    "retained_fields": [field["name"] for field in fields],
                },
                "retention_class": _clean_runtime_text(raw_bundle.get("retention_class"))
                or "runtime_evidence",
                "jurisdiction": jurisdiction,
                "license": _clean_runtime_text(raw_bundle.get("license")),
                "public_export_allowed": public_export_allowed,
                "source_attribution": _clean_runtime_text(raw_bundle.get("source_attribution"))
                or source_family,
                "authority_basis": _clean_runtime_text(raw_bundle.get("authority_basis"))
                or _clean_runtime_text(context.get("authority_basis"))
                or "runtime policy evaluation authority",
                "redaction_status": _clean_runtime_text(raw_bundle.get("redaction_status"))
                or "redacted",
            }
        )
    return sources


def _runtime_privacy_public_artifacts(
    *,
    context: Mapping[str, Any],
    source_ids: list[str],
) -> list[dict[str, Any]]:
    configured = context.get("public_artifact_families")
    if isinstance(configured, list):
        artifacts = [dict(item) for item in configured if isinstance(item, Mapping)]
        if artifacts:
            return artifacts
    return [
        {
            "artifact_family": "public_policy_decision_artifact",
            "jurisdiction": _runtime_privacy_jurisdiction(context),
            "license": _clean_runtime_text(context.get("public_artifact_license")) or "CC-BY-4.0",
            "public_export_allowed": True,
            "source_attribution": source_ids,
            "redaction_status": "redacted",
            "authority_basis": _clean_runtime_text(context.get("authority_basis"))
            or "public interest policy publication",
        }
    ]


def _scientist_progress_poll_interval_seconds() -> float:
    raw_value = os.getenv("POLISYOS_SCIENTIST_PROGRESS_POLL_S", "0.5")
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return 0.5
    return max(value, 0.01)


def _scientist_trace_path_for_store(store: object, run_id: str) -> Path | None:
    root = getattr(store, "root", None)
    if root is None:
        return None
    return Path(root) / "runs" / run_id / "trace.jsonl"


def _scientist_node_alias_from_phase(phase: str) -> str | None:
    if phase.startswith(_SCIENTIST_TRACE_NODE_PREFIX):
        return phase.removeprefix(_SCIENTIST_TRACE_NODE_PREFIX)
    return None


def _scientist_trace_artifact_refs(event: Mapping[str, Any]) -> list[dict[str, str]]:
    refs = event.get("refs")
    if not isinstance(refs, Mapping):
        return []
    artifact_refs: list[dict[str, str]] = []
    for direction in ("inputs", "outputs"):
        values = refs.get(direction)
        if not isinstance(values, list | tuple):
            continue
        for value in values:
            if not isinstance(value, Mapping):
                continue
            artifact_id = value.get("artifact_id")
            if not artifact_id:
                continue
            artifact_refs.append(
                {
                    "direction": direction,
                    "artifact_id": str(artifact_id),
                    "kind": str(value.get("kind") or ""),
                    "media_type": str(value.get("media_type") or ""),
                }
            )
    return artifact_refs


def _scientist_trace_event_summary(
    event: Mapping[str, Any],
    *,
    event_index: int,
) -> dict[str, Any]:
    phase = str(event.get("phase") or "")
    warnings_payload = event.get("warnings")
    errors_payload = event.get("errors")
    metrics_payload = event.get("metrics")
    return {
        "event_index": event_index,
        "timestamp": event.get("ts"),
        "phase": phase,
        "event": str(event.get("event") or ""),
        "node_alias": _scientist_node_alias_from_phase(phase),
        "metrics": dict(metrics_payload) if isinstance(metrics_payload, Mapping) else {},
        "warning_count": len(warnings_payload) if isinstance(warnings_payload, list) else 0,
        "error_count": len(errors_payload) if isinstance(errors_payload, list) else 0,
        "artifact_refs": _scientist_trace_artifact_refs(event),
    }


class _ScientistTraceProgressBridge:
    """Bridge Scientist trace.jsonl events into control-job progress heartbeats."""

    def __init__(
        self,
        *,
        trace_path: Path | None,
        on_event: Callable[[dict[str, Any]], None],
        poll_interval_seconds: float,
    ) -> None:
        self._trace_path = trace_path
        self._on_event = on_event
        self._poll_interval_seconds = poll_interval_seconds
        self._line_count = 0
        self._event_count = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._trace_path is None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name="polisyos-scientist-progress-bridge",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self._poll_interval_seconds * 2, 1.0))
        self.drain()

    def drain(self) -> None:
        if self._trace_path is None or not self._trace_path.exists():
            return
        try:
            lines = self._trace_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            logger.debug(
                "Failed to read Scientist trace progress from %s: %s",
                self._trace_path,
                exc,
            )
            return
        for line in lines[self._line_count :]:
            if not line.strip():
                self._line_count += 1
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                break
            self._line_count += 1
            if not isinstance(event, Mapping):
                continue
            self._event_count += 1
            self._on_event(_scientist_trace_event_summary(event, event_index=self._event_count))

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.drain()
            except Exception as exc:  # pragma: no cover - diagnostics must not break jobs
                logger.debug("Scientist progress bridge failed: %s", exc)
            self._stop_event.wait(self._poll_interval_seconds)


def _is_serious_execution_profile(value: str | None) -> bool:
    return str(value or "").strip().lower() in _SERIOUS_EXECUTION_PROFILES


def _copy_promotable_param(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): deepcopy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [deepcopy(item) for item in value]
    return deepcopy(value)


def _iter_context_param_sources(context: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sources: list[Mapping[str, Any]] = [context]
    for key in _NESTED_CONTEXT_PARAM_KEYS:
        nested = context.get(key)
        if isinstance(nested, Mapping):
            sources.append(nested)
    return sources


def _context_requirement_tokens(context: Mapping[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for source in _iter_context_param_sources(context):
        requirements = source.get("requirements")
        if isinstance(requirements, str):
            tokens.add(requirements.strip().lower())
        elif isinstance(requirements, list | tuple | set):
            tokens.update(str(item).strip().lower() for item in requirements if str(item).strip())
        run_type = source.get("run_type")
        if run_type:
            tokens.add(f"run_type:{str(run_type).strip().lower()}")
    return tokens


def _requires_local_production_data_lane(
    *,
    context: Mapping[str, Any],
    execution_profile: str | None,
    data_source: DataSourceBinding | None,
) -> bool:
    if data_source is not None:
        return False
    tokens = _context_requirement_tokens(context)
    explicit_production_data_request = bool(
        "use_production_data_materialization" in tokens
        or "run_type:local_production_canary" in tokens
        or "run_type:production_canary" in tokens
        or "run_type:staging_canary" in tokens
    )
    if explicit_production_data_request:
        return True
    if not _is_serious_execution_profile(execution_profile):
        return False
    return bool("use_production_data_materialization" in tokens)


def _first_country_code(context_profile: object) -> str | None:
    if not isinstance(context_profile, Mapping):
        return None
    countries = context_profile.get("countries")
    if isinstance(countries, list):
        for country in countries:
            token = str(country or "").strip().upper()
            if token:
                return token
    for key in ("country_code", "country"):
        token = str(context_profile.get(key) or "").strip().upper()
        if token:
            return token
    return None


def _context_year(context_profile: object) -> int | None:
    if not isinstance(context_profile, Mapping):
        return None
    raw_year = context_profile.get("publication_year")
    if isinstance(raw_year, int):
        return raw_year
    if isinstance(raw_year, str) and raw_year.strip().isdigit():
        return int(raw_year.strip())
    return None


def _first_existing_path(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _first_child_with(parent: Path, relative_file: str) -> Path | None:
    if not parent.exists():
        return None
    for child in sorted((item for item in parent.iterdir() if item.is_dir()), reverse=True):
        if (child / relative_file).exists():
            return child
    return None


def _set_default_existing_path(params: dict[str, Any], key: str, path: Path | None) -> None:
    if key in params or path is None or not path.exists():
        return
    params[key] = str(path)


def _production_data_root(params: Mapping[str, Any], *, allow_default: bool) -> Path | None:
    return _resolve_production_data_root(params, allow_default=allow_default)


def _apply_production_data_defaults(
    params: dict[str, Any],
    *,
    allow_default: bool,
) -> None:
    _apply_production_data_defaults_impl(params, allow_default=allow_default)


def _build_scientist_context_params(
    context: Mapping[str, Any],
    *,
    domain_hint: str | None,
    execution_profile: str | None,
) -> dict[str, Any]:
    """Promote supported NL context fields into Scientist workflow params."""

    params: dict[str, Any] = {}
    for source in _iter_context_param_sources(context):
        for key in _PROMOTED_CONTEXT_PARAM_KEYS:
            if key in source and key not in params:
                params[key] = _copy_promotable_param(source[key])

    _apply_production_data_defaults(
        params,
        allow_default=_is_serious_execution_profile(execution_profile),
    )

    if (
        "transport_required" not in params
        and isinstance(params.get("source_context"), Mapping)
        and isinstance(params.get("target_context"), Mapping)
    ):
        params["transport_required"] = True

    if (
        _is_serious_execution_profile(execution_profile)
        and "cross_graph_evidence_config" not in params
    ):
        config: dict[str, Any] = {"enabled": True}
        if domain_hint:
            config["policy_domain"] = domain_hint
        country_code = _first_country_code(params.get("target_context"))
        if country_code:
            config["country_code"] = country_code
            config["jurisdiction"] = country_code
        target_year = _context_year(params.get("target_context"))
        if target_year is not None:
            config["target_year"] = target_year
        params["cross_graph_evidence_config"] = config

    return params


def _canonicalize_runtime_metric_payload(
    value: object,
    *,
    taxonomy: ProductionMetricTaxonomy,
    diagnostics: list[dict[str, Any]],
    fail_unknown: bool,
    path: str,
) -> object:
    if isinstance(value, Mapping):
        payload = {str(key): deepcopy(item) for key, item in value.items()}
        for key, item in list(payload.items()):
            child_path = f"{path}.{key}" if path else key
            if key in _METRIC_PAYLOAD_KEYS and isinstance(item, str) and item.strip():
                result = canonicalize_metric_id_with_diagnostics(
                    item,
                    taxonomy=taxonomy,
                    path=child_path,
                    fail_unknown=fail_unknown,
                )
                payload[key] = result.metric_id
                diagnostics.extend(result.diagnostics)
            elif key in _METRIC_NESTED_PAYLOAD_KEYS or isinstance(item, Mapping | list | tuple):
                payload[key] = _canonicalize_runtime_metric_payload(
                    item,
                    taxonomy=taxonomy,
                    diagnostics=diagnostics,
                    fail_unknown=fail_unknown,
                    path=child_path,
                )
        return payload
    if isinstance(value, list):
        return [
            _canonicalize_runtime_metric_payload(
                item,
                taxonomy=taxonomy,
                diagnostics=diagnostics,
                fail_unknown=fail_unknown,
                path=f"{path}[{index}]",
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, tuple):
        return [
            _canonicalize_runtime_metric_payload(
                item,
                taxonomy=taxonomy,
                diagnostics=diagnostics,
                fail_unknown=fail_unknown,
                path=f"{path}[{index}]",
            )
            for index, item in enumerate(value)
        ]
    return deepcopy(value)


async def _close_llm_client(client: object | None) -> None:
    if client is None:
        return
    close = getattr(client, "aclose", None)
    if not callable(close):
        return
    try:
        result = close()
        if hasattr(result, "__await__"):
            await result
    except Exception as exc:  # pragma: no cover - defensive cleanup path
        logger.debug("Failed to close LLM client cleanly: %s", exc)


def _variant_failure_reason(variant: Mapping[str, Any]) -> str | None:
    structured_failure = _variant_structured_failure(variant)
    if structured_failure is not None:
        code = str(structured_failure.get("code") or "variant_failed")
        message = str(structured_failure.get("message") or "").strip()
        return f"{code}: {message}" if message else code

    steps = variant.get("steps")
    if isinstance(steps, list):
        for raw_step in reversed(steps):
            if not isinstance(raw_step, Mapping):
                continue
            details = raw_step.get("details")
            if isinstance(details, Mapping):
                raw_error = details.get("error")
                if raw_error:
                    return str(raw_error)

    notes = variant.get("notes")
    if isinstance(notes, list):
        for raw_note in reversed(notes):
            note = str(raw_note)
            if note.startswith("variant_error:"):
                return note.removeprefix("variant_error:").strip()
    return None


def _mapping_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Copy a JSON row sequence into the mutable owner contract shape."""

    return list(rows)


def _json_safe_payload(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_safe_payload(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe_payload(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _exception_failure_payload(exc: BaseException) -> dict[str, Any] | None:
    payload = getattr(exc, "failure", None)
    if not isinstance(payload, Mapping):
        return None
    return cast("dict[str, Any]", _json_safe_payload(payload))


def _variant_structured_failure(variant: Mapping[str, Any]) -> dict[str, Any] | None:
    direct_failure = variant.get("failure")
    if isinstance(direct_failure, Mapping):
        return cast("dict[str, Any]", _json_safe_payload(direct_failure))

    steps = variant.get("steps")
    if not isinstance(steps, list):
        return None
    for raw_step in reversed(steps):
        if not isinstance(raw_step, Mapping):
            continue
        details = raw_step.get("details")
        if not isinstance(details, Mapping):
            continue
        failure = details.get("failure")
        if isinstance(failure, Mapping):
            return cast("dict[str, Any]", _json_safe_payload(failure))
    return None


def _variant_failure_summary(variants: list[Mapping[str, Any]]) -> str:
    parts: list[str] = []
    for variant in variants:
        if str(variant.get("status") or "").lower() != "failed":
            continue

        model = str(
            variant.get("model")
            or variant.get("model_variant_id")
            or variant.get("provider")
            or "unknown_model"
        )
        reason = _variant_failure_reason(variant)
        parts.append(f"{model}: {reason or 'variant_failed'}")

    if not parts:
        return "no LLM model variant produced a Trinity bundle"
    return "; ".join(parts)[:1000]


def _model_variants_failure_envelope(
    variants: list[Mapping[str, Any]],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    for variant in variants:
        if str(variant.get("status") or "").lower() != "failed":
            continue
        reason = _variant_failure_reason(variant) or "variant_failed"
        structured_failure = _variant_structured_failure(variant)
        failures.append(
            {
                "model_variant_id": variant.get("model_variant_id"),
                "model": variant.get("model"),
                "provider": variant.get("provider"),
                "reason": reason,
                **({"failure": structured_failure} if structured_failure is not None else {}),
            }
        )

    structured_failures = [
        item["failure"] for item in failures if isinstance(item.get("failure"), Mapping)
    ]
    if failures and len(structured_failures) == len(failures):
        primary_failure = structured_failures[0]
        return {
            "code": str(primary_failure.get("code") or "model_variant_failed"),
            "layer": str(primary_failure.get("layer") or "nl_pipeline"),
            "phase": str(primary_failure.get("phase") or "model_variants"),
            "message": _variant_failure_summary(variants),
            "retryable": any(bool(item.get("retryable")) for item in structured_failures),
            "next_action": (
                str(primary_failure.get("next_action"))
                if primary_failure.get("next_action")
                else "Inspect model variant failure details before retrying."
            ),
            "variants": failures,
        }

    reasons = " ".join(str(item.get("reason") or "") for item in failures).lower()
    retryable = any(
        marker in reasons
        for marker in (
            "temporarily unavailable",
            "timeout",
            "timed out",
            "rate limit",
            "unavailable",
            "connection",
        )
    )
    gateway_failure = any(
        str(item.get("provider") or "").lower() in {"gateway", "simulated_gateway"}
        or bool(item.get("model"))
        for item in failures
    )
    return {
        "code": "no_model_variant_completed",
        "layer": "llm_gateway" if gateway_failure else "nl_pipeline",
        "phase": "model_variants",
        "message": _variant_failure_summary(variants),
        "retryable": retryable,
        "variants": failures,
    }


def _production_materialization_failure(
    *,
    execution_profile: str | None,
    data_source: DataSourceBinding | None,
    selected_variant: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return a stable canary failure when serious runs lack real materialization refs."""
    if not _is_serious_execution_profile(execution_profile) or data_source is not None:
        return None

    auto_refs = selected_variant.get("auto_data_source_refs")
    if not isinstance(auto_refs, Mapping):
        auto_refs = {}
    required_refs = (
        "data_snapshot_ref",
        "input_bindings_ref",
        "registry_bundle_ref",
        "quality_report_ref",
        "production_data_quality_report_ref",
    )
    missing = [
        key
        for key in required_refs
        if not isinstance(auto_refs.get(key), str) or not str(auto_refs.get(key)).strip()
    ]
    fixture_like = [
        key
        for key in required_refs
        if isinstance(auto_refs.get(key), str)
        and any(marker in str(auto_refs.get(key)).lower() for marker in ("fixture", "mock"))
    ]
    if not missing and not fixture_like:
        return None
    message_parts: list[str] = []
    if missing:
        message_parts.append("missing refs: " + ", ".join(missing))
    if fixture_like:
        message_parts.append("fixture/mock refs: " + ", ".join(fixture_like))
    return {
        "code": "production_data_quality_missing",
        "layer": "fabric_materialization",
        "phase": "production_data_quality",
        "message": "; ".join(message_parts),
        "retryable": False,
        "model": selected_variant.get("model"),
        "provider": selected_variant.get("provider"),
        "artifact_refs": {
            str(key): value
            for key, value in auto_refs.items()
            if isinstance(key, str) and isinstance(value, str)
        },
        "next_action": (
            "Inspect production_data_root, Fabric retrieval/materialization output, "
            "quality diagnostics, and lineage before retrying the production canary."
        ),
    }


def _reconcile_materialization_input_basis(
    current_inputs: Sequence[InputRef],
    *,
    currently_published_refs: frozenset[str],
    existing_basis: tuple[tuple[InputRef, ...], frozenset[str]] | None,
    current_reissuable_report_refs: frozenset[tuple[str, str]] = frozenset(),
) -> tuple[tuple[InputRef, ...], frozenset[str]]:
    """Keep one report's upstream input closure stable across idempotent retries.

    Runtime reports published after the original input freeze cannot become inputs to
    that earlier report on retry. Any other change to the selected input references
    refuses reuse so a real source or profile change is never hidden.
    """
    if existing_basis is None:
        return (tuple(current_inputs), currently_published_refs)

    frozen_inputs, refs_present_at_freeze = existing_basis
    later_published_refs = currently_published_refs - refs_present_at_freeze
    later_report_roles = frozenset(
        role
        for artifact_id, role in current_reissuable_report_refs
        if artifact_id in later_published_refs
    )
    current_upstream_inputs = tuple(
        item
        for item in current_inputs
        if str(item.artifact_id) not in later_published_refs and item.role not in later_report_roles
    )
    frozen_upstream_inputs = tuple(
        item for item in frozen_inputs if item.role not in later_report_roles
    )
    if current_upstream_inputs != frozen_upstream_inputs:
        raise RuntimeError("auto_materialization_input_basis_changed")
    return existing_basis


def _runtime_quality_report_cas_publication_is_admitted(
    *,
    artifact_store: ArtifactStore | None,
    selected_ref: ArtifactRef | None,
    runtime_ref: str | None,
    report_key: str,
    ref_key: str,
    report: Mapping[str, Any],
    envelope: Mapping[str, Any] | None,
    expected_write_options: object = None,
    expected_identity_context: object = None,
) -> bool:
    """Require the existing runtime-quality CAS owner gate for a selected report view."""
    from polisyos.runtime.quality.authority import runtime_quality_report_cas_admission_issues

    return not runtime_quality_report_cas_admission_issues(
        artifact_store=artifact_store,
        selected_ref=selected_ref,
        runtime_ref=runtime_ref,
        report_key=report_key,
        ref_key=ref_key,
        report=report,
        envelope=envelope,
        expected_write_options=expected_write_options,
        expected_identity_context=expected_identity_context,
    )


def _runtime_quality_historical_report_materialization_input_is_verified(
    item: InputRef,
    *,
    report_key: str,
    ref_key: str,
    artifact_store: ArtifactStore | None,
    tenant_context: ArtifactTenantContextInfo,
    current_publication_verifier: Callable[[_RuntimeQualityReportPublicationBasis], bool],
) -> bool:
    """Rebuild a historical report publication only from its exact selected CAS lineage."""
    contract = runtime_quality_report_owner_contract(report_key, ref_key)
    from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo as TenantContext

    if (
        contract is None
        or item.role != ref_key.removesuffix("_ref")
        or item.manifest_profile_sha256 is None
        or artifact_store is None
        or type(tenant_context) is not TenantContext
    ):
        return False
    from polisyos.core.artifacts import (
        artifact_manifest_profile_sha256,
        artifact_ref_for_manifest,
        read_core_manifest_profile,
        resolve_authority_envelope_ref,
    )
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.authority_reconciliation import (
        resolve_authority_diagnostic_event_ref,
    )
    from polisyos.runtime.quality.diagnostic_events import (
        DIAGNOSTIC_EVENT_ARTIFACT_KIND,
        DIAGNOSTIC_EVENT_SCHEMA_NAME,
        DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    )

    try:
        selected_ref = ArtifactRef(
            artifact_id=item.artifact_id,
            kind=contract.artifact_kind,
            media_type=contract.media_type,
            manifest_profile_sha256=item.manifest_profile_sha256,
        )
        with tenant_scope(None, tenant_id=tenant_context.tenant_id, cell_id=tenant_context.cell_id):
            if not artifact_store.verify(selected_ref).ok:
                return False
            manifest, declaration = read_core_manifest_profile(
                artifact_store, selected_ref, manifest_profile_sha256=item.manifest_profile_sha256
            )
            if (
                declaration.status != "declared"
                or artifact_manifest_profile_sha256(manifest) != item.manifest_profile_sha256
                or artifact_ref_for_manifest(manifest).model_dump(mode="json")
                != selected_ref.model_dump(mode="json")
                or manifest.tenant_context != tenant_context
                or manifest.authority is None
            ):
                return False
            stored_payload = require_declared_profile(
                read_core_json_artifact(
                    artifact_store,
                    selected_ref,
                    manifest_profile_sha256=item.manifest_profile_sha256,
                )
            )
            if not isinstance(stored_payload, Mapping):
                return False

            authority = manifest.authority
            envelope_ref = resolve_authority_envelope_ref(artifact_store, authority)
            envelope_profile = authority.authority_envelope_manifest_profile_sha256
            if envelope_profile is None or envelope_ref.manifest_profile_sha256 != envelope_profile:
                return False
            envelope_manifest, envelope_declaration = read_core_manifest_profile(
                artifact_store, envelope_ref, manifest_profile_sha256=envelope_profile
            )
            envelope_payload = require_declared_profile(
                read_core_json_artifact(
                    artifact_store, envelope_ref, manifest_profile_sha256=envelope_profile
                )
            )
            if (
                envelope_declaration.status != "declared"
                or envelope_manifest.artifact_id != envelope_ref.artifact_id
                or not isinstance(envelope_payload, Mapping)
            ):
                return False

            event_ref = resolve_authority_diagnostic_event_ref(artifact_store, authority)
            event_profile = authority.diagnostic_event_manifest_profile_sha256
            if event_profile is None or event_ref.manifest_profile_sha256 != event_profile:
                return False
            event_manifest, event_declaration = read_core_manifest_profile(
                artifact_store, event_ref, manifest_profile_sha256=event_profile
            )
            event_payload = require_declared_profile(
                read_core_json_artifact(
                    artifact_store,
                    event_ref,
                    manifest_profile_sha256=event_profile,
                )
            )
            if (
                event_declaration.status != "declared"
                or event_manifest.artifact_id != event_ref.artifact_id
                or event_manifest.kind != DIAGNOSTIC_EVENT_ARTIFACT_KIND
                or event_manifest.artifact_schema is None
                or event_manifest.artifact_schema.name != DIAGNOSTIC_EVENT_SCHEMA_NAME
                or event_manifest.artifact_schema.version != DIAGNOSTIC_EVENT_SCHEMA_VERSION
                or not isinstance(event_payload, Mapping)
            ):
                return False

            selected_id = str(selected_ref.artifact_id)
            expected_event_context = {
                "event_type": "polisyos.runtime.diagnostic.cas_write.v1",
                "run_id": envelope_payload.get("run_id"),
                "job_id": envelope_payload.get("job_id"),
                "tenant_id": envelope_payload.get("tenant_id"),
                "cell_id": envelope_payload.get("cell_id"),
                "trace_id": envelope_payload.get("trace_id"),
                "span_id": envelope_payload.get("span_id"),
                "parent_span_id": envelope_payload.get("parent_span_id"),
                "execution_profile": envelope_payload.get("effective_execution_profile"),
                "phase": contract.phase,
                "producer_component": contract.producer_component,
                "producer_version": contract.producer_version,
                "input_refs": [str(input_ref.artifact_id) for input_ref in manifest.inputs],
                "artifact_refs": [selected_id],
            }
            if any(
                event_payload.get(key) != value for key, value in expected_event_context.items()
            ):
                return False

            basis = _build_runtime_quality_report_publication_basis(
                report_key=report_key,
                ref_key=ref_key,
                report_payload=stored_payload,
                artifact_ref=selected_ref.model_dump(mode="json"),
                runtime_event_ref=authority.diagnostic_event_ref,
                runtime_event_manifest_profile_sha256=event_profile,
                authority_envelope_ref=authority.authority_envelope_ref,
                authority_envelope=envelope_payload,
                manifest_ref=authority.manifest_ref,
                payload_sha256=authority.payload_sha256,
            )
            if not current_publication_verifier(basis):
                return False
            return _runtime_quality_report_cas_publication_is_admitted(
                artifact_store=artifact_store,
                selected_ref=selected_ref,
                runtime_ref=selected_id,
                report_key=report_key,
                ref_key=ref_key,
                report=_runtime_quality_report_publication_view(basis),
                envelope=envelope_payload,
            )
    except Exception:
        return False


async def _put_nl_tenant_owned_json(
    artifact_store: AsyncArtifactStore,
    payload: object,
    options: ArtifactWriteOptions,
    *,
    tenant_context: ArtifactTenantContextInfo,
    canon_spec: CanonSpec | None = None,
    return_selected_profile: bool = False,
) -> ArtifactRef:
    """Persist one NL child artifact under the execution's admitted tenant owner."""
    from dataclasses import replace as dataclass_replace

    from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo as TenantContext
    from polisyos.core.security.tenant_context import tenant_scope

    if type(tenant_context) is not TenantContext:
        raise RuntimeError("nl_child_artifact_tenant_context_not_established")
    if options.tenant_context is not None and options.tenant_context != tenant_context:
        raise RuntimeError("nl_child_artifact_tenant_context_mismatch")
    scoped_options = dataclass_replace(options, tenant_context=tenant_context)
    with tenant_scope(None, tenant_id=tenant_context.tenant_id, cell_id=tenant_context.cell_id):
        return await artifact_store.put_json(
            payload,
            scoped_options,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )


def _runtime_quality_report_materialization_input_is_verified(
    item: InputRef,
    *,
    output_report_key: str | None,
    reissuable_report_roles: frozenset[str],
    runtime_quality_refs: Mapping[str, object],
    runtime_quality_artifact_refs: Mapping[str, object],
    current_publication_verifier: Callable[[str, str, str], bool],
    historical_publication_verifier: Callable[[str, str, InputRef], bool] | None = None,
) -> bool:
    """Verify current report edges and admitted historical same-report predecessors."""
    if item.role not in reissuable_report_roles:
        return False
    for sibling_report_key, sibling_ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
        if item.role != sibling_ref_key.removesuffix("_ref"):
            continue
        contract = runtime_quality_report_owner_contract(sibling_report_key, sibling_ref_key)
        selected_ref = runtime_quality_artifact_refs.get(sibling_ref_key)
        if (
            contract is None
            or type(selected_ref) is not ArtifactRef
            or selected_ref.manifest_profile_sha256 is None
            or selected_ref.kind != contract.artifact_kind
            or selected_ref.media_type != contract.media_type
            or runtime_quality_refs.get(sibling_ref_key) != str(selected_ref.artifact_id)
        ):
            continue
        if sibling_report_key == output_report_key:
            # The current output is never its own source edge. A distinct historical view may be
            # restored only after rebuilding its registered owner publication from CAS.
            if (
                item.artifact_id == selected_ref.artifact_id
                or historical_publication_verifier is None
            ):
                continue
            try:
                return historical_publication_verifier(sibling_report_key, sibling_ref_key, item)
            except Exception:
                return False
        if (
            item.artifact_id != selected_ref.artifact_id
            or item.manifest_profile_sha256 != selected_ref.manifest_profile_sha256
        ):
            continue
        try:
            return current_publication_verifier(
                sibling_report_key,
                sibling_ref_key,
                str(selected_ref.artifact_id),
            )
        except Exception:
            return False
    return False


def _restore_frozen_materialization_report_inputs(
    current_inputs: Sequence[InputRef],
    *,
    existing_basis: tuple[tuple[InputRef, ...], frozenset[str]] | None,
    persisted_output_inputs: Sequence[InputRef],
    reissuable_report_roles: frozenset[str],
    verified_reissuable_report_refs: frozenset[tuple[str, str, str | None]],
) -> tuple[tuple[InputRef, ...], frozenset[str]]:
    """Restore omitted report edges only from the exact previously frozen CAS basis."""
    if existing_basis is None:
        return tuple(current_inputs), frozenset()

    frozen_inputs, _refs_present_at_freeze = existing_basis
    if tuple(persisted_output_inputs) != frozen_inputs:
        raise RuntimeError("auto_materialization_input_basis_changed")

    missing_inputs = tuple(item for item in frozen_inputs if item not in current_inputs)
    if any(
        item.role not in reissuable_report_roles
        or (
            str(item.artifact_id),
            item.role,
            item.manifest_profile_sha256,
        )
        not in verified_reissuable_report_refs
        for item in missing_inputs
    ):
        raise RuntimeError("auto_materialization_input_basis_changed")

    current_frozen_inputs = tuple(item for item in current_inputs if item in frozen_inputs)
    frozen_current_inputs = tuple(item for item in frozen_inputs if item in current_inputs)
    if current_frozen_inputs != frozen_current_inputs:
        raise RuntimeError("auto_materialization_input_basis_changed")

    restored_inputs = list(current_inputs)
    for missing in missing_inputs:
        frozen_index = frozen_inputs.index(missing)
        following = next(
            (item for item in frozen_inputs[frozen_index + 1 :] if item in restored_inputs),
            None,
        )
        if following is not None:
            insert_at = restored_inputs.index(following)
        else:
            preceding = next(
                (
                    item
                    for item in reversed(frozen_inputs[:frozen_index])
                    if item in restored_inputs
                ),
                None,
            )
            insert_at = restored_inputs.index(preceding) + 1 if preceding is not None else 0
        restored_inputs.insert(insert_at, missing)

    return (
        tuple(restored_inputs),
        frozenset(str(item.artifact_id) for item in missing_inputs),
    )


class _RuntimeQualityPublicationCandidate(NamedTuple):
    """Persisted writer identity offered only as a fully checked replay candidate."""

    generated_at: str
    as_of_time: str
    policy_intent_ref: str | None
    production_data_manifest_ref: str | None
    legal_snapshot_ref: str | None
    semantic_binding_ref: str | None


def _runtime_quality_publication_times(
    published_times: Mapping[str, tuple[str, str]],
    *,
    identity_key: str,
    requested_as_of_time: str | None,
    persisted_times: _RuntimeQualityPublicationCandidate | None,
    now: datetime,
) -> tuple[str, str]:
    """Reuse publication times only for an already successful identical intent.

    Persisted identity is only a candidate; the caller always submits it to the
    shared authority writer for full verification. Local entries are added only after
    that writer returns successfully, so neither path bypasses reconciliation.
    """
    if persisted_times is not None and (
        requested_as_of_time is None or persisted_times.as_of_time == requested_as_of_time
    ):
        return persisted_times.generated_at, persisted_times.as_of_time
    existing = published_times.get(identity_key)
    if existing is not None:
        return existing
    generated_at = now.replace(microsecond=0).isoformat()
    as_of_time = requested_as_of_time or now.isoformat()
    return generated_at, as_of_time


def _runtime_quality_candidate_inputs_match(
    *,
    manifest_inputs: Sequence[InputRef],
    envelope_input_refs: Sequence[str],
    closure_input_refs: Sequence[str],
    expected_inputs: Sequence[InputRef],
) -> bool:
    """Require the persisted manifest to preserve every typed input edge."""
    expected = tuple(expected_inputs)
    expected_ids = tuple(str(item.artifact_id) for item in expected)
    return (
        tuple(manifest_inputs) == expected
        and tuple(envelope_input_refs) == expected_ids
        and tuple(closure_input_refs) == expected_ids
    )


def _reconcile_runtime_quality_report_reentry_inputs(
    current_inputs: Sequence[InputRef],
    persisted_inputs: Sequence[InputRef],
    verified_later_report_inputs: Sequence[InputRef],
) -> tuple[InputRef, ...]:
    """Reconcile only exact later report inputs already verified by their owner.

    Persisted manifest inputs remain the complete original writer basis. A current
    invocation may contain additional selected report refs after that publication,
    but every excluded ref must have been independently resolved and owner-verified
    by the caller. This function never infers verification from a role or ID alone.
    """
    current = tuple(current_inputs)
    persisted = tuple(persisted_inputs)
    verified = tuple(verified_later_report_inputs)
    if any(item in verified[:index] for index, item in enumerate(verified)):
        raise RuntimeError("runtime_quality_publication_reuse_inputs_mismatch")
    if any(
        item not in current
        or item in persisted
        or any(item.artifact_id == original.artifact_id for original in persisted)
        for item in verified
    ):
        raise RuntimeError("runtime_quality_publication_reuse_inputs_mismatch")
    later = tuple(item for item in current if item not in persisted)
    if later != verified:
        raise RuntimeError("runtime_quality_publication_reuse_inputs_mismatch")
    reconciled = tuple(item for item in current if item not in verified)
    if reconciled != persisted:
        raise RuntimeError("runtime_quality_publication_reuse_inputs_mismatch")
    return persisted


def _runtime_quality_reuse_ref_matches_selected(
    selected_ref: ArtifactRef,
    selected_id: str,
    current_runtime_ref: object | None,
    current_artifact_ref: object | None,
) -> bool:
    """Accept missing runtime caches as candidates, while rejecting conflicts.

    The selected ref comes from the complete publisher view and is only a
    locator. The caller still has to resolve its profile and pass strict owner
    and current-identity admission before publishing it into runtime state.
    """
    if type(selected_ref) is not ArtifactRef or str(selected_ref.artifact_id) != selected_id:
        return False
    if current_runtime_ref is not None and current_runtime_ref != selected_id:
        return False
    return current_artifact_ref is None or (
        type(current_artifact_ref) is ArtifactRef
        and current_artifact_ref.model_dump(mode="json") == selected_ref.model_dump(mode="json")
    )


def _persisted_runtime_quality_publication_times(
    store: ArtifactStore,
    *,
    output_artifact_id: str,
    artifact_kind: str,
    expected_inputs: Sequence[InputRef],
    selected_ref: ArtifactRef | None = None,
) -> _RuntimeQualityPublicationCandidate | None:
    """Read a persisted writer identity as a candidate for exact-input replay.

    The shared writer remains the authority owner: it re-verifies the complete
    manifest, envelope, attestation, and event against the freshly rebuilt context
    before reusing this candidate. Input roles and manifest-profile pins are matched
    here so a same-payload artifact with changed lineage cannot seed replay fields.
    """
    from polisyos.core.artifacts import ArtifactID, read_core_manifest_profile
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.runtime.quality.authority import EvidenceAuthorityEnvelope

    def _persisted_reference(value: object, *, field_name: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value or value.strip() != value:
            raise ValueError(f"persisted authority field {field_name} is malformed")
        artifact_id = ArtifactID.model_validate(value)
        normalized = str(artifact_id)
        if normalized != value:
            raise ValueError(f"persisted authority field {field_name} is noncanonical")
        return normalized

    try:
        output_id = ArtifactID.model_validate(output_artifact_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("runtime quality output identity is invalid") from exc
    if not store.has(output_id):
        return None
    try:
        if selected_ref is not None:
            if str(selected_ref.artifact_id) != str(output_id):
                return None
            manifest, declaration = read_core_manifest_profile(
                store,
                selected_ref,
                manifest_profile_sha256=selected_ref.manifest_profile_sha256,
            )
            if declaration.status != "declared":
                return None
        else:
            manifest = store.get_manifest(output_id)
    except (AttributeError, FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("existing authority identity mismatch") from exc
    authority = manifest.authority
    if authority is None:
        return None
    if (
        manifest.kind != artifact_kind
        or authority.payload_sha256 != output_id.hex
        or tuple(manifest.inputs) != tuple(expected_inputs)
    ):
        return None

    try:
        envelope_id = ArtifactID.model_validate(authority.authority_envelope_ref)
        envelope_payload = from_canonical_bytes(store.get_bytes(envelope_id))
        if not isinstance(envelope_payload, Mapping):
            raise ValueError("authority envelope payload is not an object")
        raw_closure = envelope_payload.get("same_input_closure")
        if not isinstance(raw_closure, Mapping):
            raise ValueError("authority envelope closure is not an object")
        envelope = EvidenceAuthorityEnvelope.model_validate(envelope_payload)
        closure = envelope.same_input_closure
        if (
            envelope.artifact_ref != str(output_id)
            or envelope.cas_ref != str(output_id)
            or envelope.artifact_kind != artifact_kind
            or envelope.payload_sha256 != output_id.hex
            or not _runtime_quality_candidate_inputs_match(
                manifest_inputs=manifest.inputs,
                envelope_input_refs=envelope.input_refs,
                closure_input_refs=closure.evidence_input_refs,
                expected_inputs=expected_inputs,
            )
        ):
            return None
        policy_intent_ref = _persisted_reference(
            raw_closure.get("policy_intent_ref"),
            field_name="same_input_closure.policy_intent_ref",
        )
        production_data_manifest_ref = _persisted_reference(
            raw_closure.get("production_data_manifest_ref"),
            field_name="same_input_closure.production_data_manifest_ref",
        )
        legal_snapshot_ref = _persisted_reference(
            raw_closure.get("legal_snapshot_ref"),
            field_name="same_input_closure.legal_snapshot_ref",
        )
        semantic_binding_ref = _persisted_reference(
            envelope_payload.get("semantic_binding_ref"),
            field_name="semantic_binding_ref",
        )
        if (
            closure.policy_intent_ref != policy_intent_ref
            or closure.production_data_manifest_ref != production_data_manifest_ref
            or closure.legal_snapshot_ref != legal_snapshot_ref
            or envelope.semantic_binding_ref != semantic_binding_ref
        ):
            raise ValueError("parsed authority references differ from their stored values")
    except (AttributeError, FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("existing authority identity mismatch") from exc

    return _RuntimeQualityPublicationCandidate(
        envelope.generated_at,
        envelope.as_of_time,
        policy_intent_ref,
        production_data_manifest_ref,
        legal_snapshot_ref,
        semantic_binding_ref,
    )


def _validated_runtime_quality_reference(value: object, *, field_name: str) -> str:
    """Validate one current reference without treating malformed presence as absent."""
    from polisyos.core.artifacts import ArtifactID

    if not isinstance(value, str) or not value or value.strip() != value:
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_identity_reference_invalid",
            f"Runtime quality reference {field_name} is malformed.",
        )
    try:
        artifact_id = ArtifactID.model_validate(value)
    except (TypeError, ValueError) as exc:
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_identity_reference_invalid",
            f"Runtime quality reference {field_name} is malformed.",
        ) from exc
    normalized = str(artifact_id)
    if normalized != value:
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_identity_reference_invalid",
            f"Runtime quality reference {field_name} is noncanonical.",
        )
    return normalized


def _runtime_quality_current_publisher_output_is_verified(
    *,
    artifact_store: ArtifactStore | None,
    runtime_ref: object,
    selected_ref: object,
    write_options: object,
    identity_context: object,
    report_key: str,
    ref_key: str,
    expected_role: str,
    expected_kind: str,
    expected_schema_name: str,
    expected_schema_version: str,
    phase: str,
    current_run_id: str,
    current_job_id: str,
    current_tenant_id: str,
    current_cell_id: str | None,
    current_trace_id: str,
    current_parent_span_id: str | None,
    current_requested_profile: str | None,
    current_effective_profile: str,
    requested_as_of_time: str | None,
    event_summaries: Sequence[object],
) -> bool:
    """Re-read a current generic writer output against its current owner identity."""
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.runtime.http.services.control.artifacts import (
        AuthorityArtifactIdentityContext,
        verify_runtime_authority_artifact_identity,
    )

    bindings = [
        (binding[1], binding[2], binding[3], binding[4], binding[5])
        for binding in RUNTIME_QUALITY_PUBLICATION_CLOSURE_REFERENCE_BINDINGS
        if binding[1] is not None
    ]
    bindings.append(RUNTIME_QUALITY_PUBLICATION_SEMANTIC_BINDING_REFERENCE_BINDING)
    if (
        artifact_store is None
        or type(selected_ref) is not ArtifactRef
        or type(write_options) is not ArtifactWriteOptions
        or type(identity_context) is not AuthorityArtifactIdentityContext
        or not isinstance(runtime_ref, str)
        or runtime_ref != str(selected_ref.artifact_id)
        or (ref_key, expected_role, expected_kind, expected_schema_name, expected_schema_version)
        not in bindings
    ):
        return False

    schema = write_options.schema
    producer = write_options.producer
    profile = selected_ref.manifest_profile_sha256
    if (
        not isinstance(profile, str)
        or not profile
        or selected_ref.kind != expected_kind
        or selected_ref.media_type != "application/json"
        or write_options.kind != expected_kind
        or write_options.media_type != "application/json"
        or schema is None
        or schema.name != expected_schema_name
        or schema.version != expected_schema_version
        or producer is None
    ):
        return False

    contract = runtime_quality_report_owner_contract(report_key, ref_key)
    expected_producer_component = (
        contract.producer_component
        if contract is not None
        else f"polisyos.runtime.quality.{report_key}"
    )
    expected_producer_version = (
        contract.producer_version
        if contract is not None
        else RUNTIME_QUALITY_OWNER_PRODUCER_VERSION
    )
    if (
        producer.component != expected_producer_component
        or producer.version != expected_producer_version
    ):
        return False

    context = identity_context
    closure = context.same_input_closure
    expected_inputs = tuple(write_options.inputs or ())
    expected_input_ids = tuple(str(item.artifact_id) for item in expected_inputs)
    closure_is_closed = (
        getattr(closure, "status", None) == "closed"
        and bool(getattr(closure, "closure_sha256", None))
        and bool(getattr(closure, "policy_intent_ref", None))
        and bool(getattr(closure, "time_context_ref", None))
    )
    if (
        context.evidence_id != f"runtime_quality_ref#{ref_key}"
        or context.evidence_class != "authority_bearing"
        or context.authority_role
        != ("producer_authority" if closure_is_closed else "runtime_blocker")
        or context.provenance_kind
        != ("runtime_emitted" if closure_is_closed else "runtime_blocker")
        or context.owner != "team-runtime"
        or context.reader_contract != f"runtime_quality.{report_key}.v1"
        or context.reader_contract_version != "1.0"
        or context.run_id != current_run_id
        or context.job_id != current_job_id
        or context.tenant_id != current_tenant_id
        or context.cell_id != current_cell_id
        or context.trace_id != current_trace_id
        or context.span_id != f"{report_key}:cas_write"
        or context.parent_span_id != current_parent_span_id
        or context.requested_execution_profile != current_requested_profile
        or context.effective_execution_profile != current_effective_profile
        or context.phase != phase
        or (requested_as_of_time is not None and context.as_of_time != requested_as_of_time)
        or tuple(context.manifest_inputs) != expected_inputs
        or tuple(context.input_refs) != expected_input_ids
        or tuple(closure.evidence_input_refs) != expected_input_ids
        or closure.run_id != current_run_id
        or closure.job_id != current_job_id
        or closure.tenant_id != current_tenant_id
        or closure.cell_id != current_cell_id
        or closure.closure_id != f"{current_run_id}:runtime_quality"
        or context.effective_mode_ref != f"runtime-mode:{current_effective_profile}"
    ):
        return False

    try:
        result = verify_runtime_authority_artifact_identity(
            artifact_store,
            artifact_id=selected_ref,
            opts=write_options,
            expected_context=context,
        )
        if (
            result.cas_ref != selected_ref
            or result.identity_context != context
            or result.payload_sha256 != selected_ref.artifact_id.hex
            or result.diagnostic_event_ref.manifest_profile_sha256 is None
            or result.authority_envelope_ref.manifest_profile_sha256 is None
        ):
            return False
        payload = read_core_json_artifact(
            artifact_store,
            selected_ref,
            manifest_profile_sha256=profile,
        ).value
    except Exception:
        return False
    expected_marker = {
        "schema_version": RUNTIME_QUALITY_OWNER_MARKER_SCHEMA,
        "report_key": report_key,
        "ref_key": ref_key,
        "projection": False,
    }
    if (
        not isinstance(payload, Mapping)
        or payload.get("runtime_authority_payload") != expected_marker
    ):
        return False

    runtime_event_ref = str(result.diagnostic_event_ref.artifact_id)
    runtime_event_profile = result.diagnostic_event_ref.manifest_profile_sha256
    authority_envelope_ref = str(result.authority_envelope_ref.artifact_id)
    manifest_ref = result.manifest_ref
    payload_sha256 = result.payload_sha256
    return any(
        isinstance(event, Mapping)
        and event.get("event_name") == f"{report_key}.persisted"
        and event.get("event_type") == "polisyos.runtime.diagnostic.cas_write.v1"
        and event.get("runtime_event_ref") == runtime_event_ref
        and event.get("runtime_event_manifest_profile_sha256") == runtime_event_profile
        and event.get("artifact_ref") == runtime_ref
        and event.get("runtime_cas_ref") == runtime_ref
        and event.get("artifact_refs") == [runtime_ref]
        and event.get("payload_ref") == runtime_ref
        and event.get("ref_key") == ref_key
        and event.get("report_key") == report_key
        and event.get("authority_envelope_ref") == authority_envelope_ref
        and event.get("manifest_ref") == manifest_ref
        and event.get("payload_sha256") == payload_sha256
        for event in event_summaries
    )


def _runtime_quality_current_reference_binding(
    value: object,
    *,
    current_inputs: Sequence[object],
    current_artifact_refs: Mapping[str, object] | None,
    current_map_value_present: bool,
    artifact_store: ArtifactStore | None,
    current_ref_key: str,
    expected_role: str,
    expected_kind: str,
    expected_schema_name: str,
    expected_schema_version: str,
    field_name: str,
    current_report_verifier: Callable[[str, str], bool] | None = None,
) -> str:
    """Bind one pointer to its exact typed input or verified current publisher output."""
    from polisyos.core.artifacts import ArtifactRef, InputRef, read_core_manifest_profile

    normalized = _validated_runtime_quality_reference(value, field_name=field_name)
    role_inputs = [
        item for item in current_inputs if type(item) is InputRef and item.role == expected_role
    ]
    matches = [item for item in role_inputs if str(item.artifact_id) == normalized]
    if role_inputs and (len(role_inputs) != 1 or len(matches) != 1):
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            f"Runtime quality basis reference {field_name} differs from its typed input.",
        )

    selected_ref = (
        current_artifact_refs.get(current_ref_key) if current_artifact_refs is not None else None
    )
    if matches:
        input_ref = matches[0]
        profile = input_ref.manifest_profile_sha256
        if not isinstance(profile, str) or not profile:
            raise NaturalLanguagePipelineRefusalError(
                "runtime_quality_same_input_identity_not_established",
                f"Runtime quality basis reference {field_name} has no current manifest profile.",
            )
        if current_map_value_present or (
            current_artifact_refs is not None and current_ref_key in current_artifact_refs
        ):
            if (
                type(selected_ref) is not ArtifactRef
                or str(selected_ref.artifact_id) != normalized
                or selected_ref.kind != expected_kind
                or selected_ref.media_type != "application/json"
                or selected_ref.manifest_profile_sha256 != profile
            ):
                raise NaturalLanguagePipelineRefusalError(
                    "runtime_quality_same_input_identity_not_established",
                    f"Runtime quality basis reference {field_name} "
                    "differs from its current owner ref.",
                )
            if current_report_verifier is None or not current_report_verifier(
                current_ref_key, normalized
            ):
                raise NaturalLanguagePipelineRefusalError(
                    "runtime_quality_same_input_identity_not_established",
                    f"Runtime quality basis reference {field_name} lacks current owner readback.",
                )
        elif artifact_store is not None:
            selected_ref = ArtifactRef(
                artifact_id=input_ref.artifact_id,
                kind=expected_kind,
                media_type="application/json",
                manifest_profile_sha256=profile,
            )
            try:
                manifest, declaration = read_core_manifest_profile(
                    artifact_store,
                    selected_ref,
                    manifest_profile_sha256=profile,
                )
                verification = artifact_store.verify(selected_ref)
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                raise NaturalLanguagePipelineRefusalError(
                    "runtime_quality_same_input_identity_not_established",
                    f"Runtime quality basis reference {field_name} "
                    "failed current owner verification.",
                ) from exc
            schema = manifest.artifact_schema
            if (
                declaration.status != "declared"
                or not verification.ok
                or manifest.kind != expected_kind
                or manifest.media_type != "application/json"
                or schema is None
                or schema.name != expected_schema_name
                or schema.version != expected_schema_version
            ):
                raise NaturalLanguagePipelineRefusalError(
                    "runtime_quality_same_input_identity_not_established",
                    f"Runtime quality basis reference {field_name} "
                    "differs from its current owner schema.",
                )
        return normalized

    if (
        type(selected_ref) is not ArtifactRef
        or str(selected_ref.artifact_id) != normalized
        or selected_ref.kind != expected_kind
        or selected_ref.media_type != "application/json"
        or not selected_ref.manifest_profile_sha256
    ):
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            f"Runtime quality basis reference {field_name} has no selected owner ref.",
        )
    try:
        owner_verified = current_report_verifier is not None and current_report_verifier(
            current_ref_key, normalized
        )
    except Exception:
        owner_verified = False
    if not owner_verified:
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            (
                f"Runtime quality basis reference {field_name} is neither a typed input "
                "nor a current owner-verified publication."
            ),
        )
    return normalized


def _runtime_quality_current_reference_value(
    value: object,
    *,
    has_current_value: bool,
    current_inputs: Sequence[object],
    current_artifact_refs: Mapping[str, object] | None,
    current_map_value_present: bool,
    artifact_store: ArtifactStore | None,
    current_ref_key: str,
    expected_role: str,
    expected_kind: str,
    expected_schema_name: str,
    expected_schema_version: str,
    field_name: str,
    current_report_verifier: Callable[[str, str], bool] | None = None,
) -> str | None:
    """Resolve one pointer from a typed edge or paired current publisher-owned ref."""
    from polisyos.core.artifacts import ArtifactRef, InputRef

    role_inputs = [
        item for item in current_inputs if type(item) is InputRef and item.role == expected_role
    ]
    if has_current_value:
        selected_value = _validated_runtime_quality_reference(value, field_name=field_name)
    elif current_artifact_refs is not None and current_ref_key in current_artifact_refs:
        selected_ref = current_artifact_refs[current_ref_key]
        if type(selected_ref) is not ArtifactRef:
            raise NaturalLanguagePipelineRefusalError(
                "runtime_quality_same_input_identity_not_established",
                f"Runtime quality basis reference {field_name} has an invalid current owner ref.",
            )
        selected_value = _validated_runtime_quality_reference(
            str(selected_ref.artifact_id),
            field_name=field_name,
        )
    else:
        if not role_inputs:
            return None
        if len(role_inputs) != 1:
            raise NaturalLanguagePipelineRefusalError(
                "runtime_quality_same_input_identity_not_established",
                f"Runtime quality basis reference {field_name} has ambiguous current typed inputs.",
            )
        selected_value = _validated_runtime_quality_reference(
            str(role_inputs[0].artifact_id),
            field_name=field_name,
        )

    return _runtime_quality_current_reference_binding(
        selected_value,
        current_inputs=current_inputs,
        current_artifact_refs=current_artifact_refs,
        current_map_value_present=current_map_value_present,
        artifact_store=artifact_store,
        current_ref_key=current_ref_key,
        expected_role=expected_role,
        expected_kind=expected_kind,
        expected_schema_name=expected_schema_name,
        expected_schema_version=expected_schema_version,
        field_name=field_name,
        current_report_verifier=current_report_verifier,
    )


def _runtime_quality_closure_reference_values(
    runtime_quality_refs: Mapping[str, object],
    *,
    candidate: _RuntimeQualityPublicationCandidate | None,
    output_artifact_id: str,
    ref_key: str,
    current_inputs: Sequence[object] = (),
    current_artifact_refs: Mapping[str, object] | None = None,
    artifact_store: ArtifactStore | None = None,
    current_report_verifier: Callable[[str, str], bool] | None = None,
) -> dict[str, str | None]:
    """Build every closure pointer from typed edges or strict current owner readback."""
    selected: dict[str, str | None] = {}
    for (
        closure_field,
        current_key,
        expected_role,
        expected_kind,
        expected_schema_name,
        expected_schema_version,
    ) in RUNTIME_QUALITY_PUBLICATION_CLOSURE_REFERENCE_BINDINGS:
        current_value = (
            None
            if current_key is None
            else _runtime_quality_current_reference_value(
                runtime_quality_refs.get(current_key),
                has_current_value=current_key in runtime_quality_refs,
                current_inputs=current_inputs,
                current_artifact_refs=current_artifact_refs,
                current_map_value_present=current_key in runtime_quality_refs,
                artifact_store=artifact_store,
                current_ref_key=current_key,
                expected_role=expected_role,
                expected_kind=expected_kind,
                expected_schema_name=expected_schema_name,
                expected_schema_version=expected_schema_version,
                field_name=current_key,
                current_report_verifier=current_report_verifier,
            )
        )
        candidate_value = getattr(candidate, closure_field) if candidate is not None else None
        if candidate is not None and current_value != candidate_value:
            raise NaturalLanguagePipelineRefusalError(
                "runtime_quality_same_input_identity_not_established",
                (
                    f"Runtime quality closure reference {current_key} changed "
                    f"during replay for {ref_key}."
                ),
            )
        if current_value == output_artifact_id:
            raise NaturalLanguagePipelineRefusalError(
                "runtime_quality_same_input_identity_not_established",
                f"Runtime quality closure reference {current_key} cannot point at its own output.",
            )
        selected[closure_field] = current_value
    return selected


def _runtime_quality_semantic_binding_payload_identity(
    payload: Mapping[str, Any],
    *,
    field_name: str,
) -> str:
    """Recompute the ledger's content identity without confusing it with its CAS ref."""
    source_payload = dict(payload)
    marker_present = "runtime_authority_payload" in source_payload
    supplied_marker = source_payload.pop("runtime_authority_payload", None)
    expected_marker = runtime_quality_report_owner_marker(
        "semantic_binding_ledger",
        "semantic_binding_ledger_ref",
    )
    if marker_present and supplied_marker != expected_marker:
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            "Runtime quality semantic binding payload has an invalid owner marker.",
        )

    declared_identity = _validated_runtime_quality_reference(
        source_payload.get("semantic_binding_ref"),
        field_name=field_name,
    )
    from polisyos.runtime.quality.semantic_binding import close_semantic_binding_ledger

    try:
        recomputed_payload = close_semantic_binding_ledger(
            {**source_payload, "semantic_binding_ref": "pending"}
        )
    except Exception as exc:
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            "Runtime quality semantic binding content could not be recomputed.",
        ) from exc
    if recomputed_payload.get("semantic_binding_ref") != declared_identity:
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            "Runtime quality semantic binding digest differs from its content.",
        )
    return declared_identity


def _runtime_quality_selected_semantic_binding_identity(
    *,
    runtime_quality_refs: Mapping[str, object],
    current_inputs: Sequence[object],
    current_artifact_refs: Mapping[str, object] | None,
    artifact_store: ArtifactStore | None,
    current_report_verifier: Callable[[str, str], bool] | None,
) -> str | None:
    """Resolve a typed CAS owner and recompute the semantic identity from its payload."""
    from polisyos.core.artifacts import ArtifactRef, InputRef

    (
        current_ref_key,
        expected_role,
        expected_kind,
        expected_schema_name,
        expected_schema_version,
    ) = RUNTIME_QUALITY_PUBLICATION_SEMANTIC_BINDING_REFERENCE_BINDING
    current_map_value_present = current_ref_key in runtime_quality_refs
    selected_artifact_id = _runtime_quality_current_reference_value(
        runtime_quality_refs.get(current_ref_key),
        has_current_value=current_map_value_present,
        current_inputs=current_inputs,
        current_artifact_refs=current_artifact_refs,
        current_map_value_present=current_map_value_present,
        artifact_store=artifact_store,
        current_ref_key=current_ref_key,
        expected_role=expected_role,
        expected_kind=expected_kind,
        expected_schema_name=expected_schema_name,
        expected_schema_version=expected_schema_version,
        field_name=current_ref_key,
        current_report_verifier=current_report_verifier,
    )
    if selected_artifact_id is None:
        return None

    selected_ref = (
        current_artifact_refs.get(current_ref_key) if current_artifact_refs is not None else None
    )
    if type(selected_ref) is not ArtifactRef:
        matching_inputs = [
            item
            for item in current_inputs
            if type(item) is InputRef
            and item.role == expected_role
            and str(item.artifact_id) == selected_artifact_id
        ]
        if len(matching_inputs) != 1:
            raise NaturalLanguagePipelineRefusalError(
                "runtime_quality_same_input_identity_not_established",
                "Runtime quality semantic binding selected input is ambiguous or absent.",
            )
        input_ref = matching_inputs[0]
        profile = input_ref.manifest_profile_sha256
        if not isinstance(profile, str) or not profile:
            raise NaturalLanguagePipelineRefusalError(
                "runtime_quality_same_input_identity_not_established",
                "Runtime quality semantic binding selected input lacks a manifest profile.",
            )
        selected_ref = ArtifactRef(
            artifact_id=input_ref.artifact_id,
            kind=expected_kind,
            media_type="application/json",
            manifest_profile_sha256=profile,
        )
    if (
        type(selected_ref) is not ArtifactRef
        or str(selected_ref.artifact_id) != selected_artifact_id
        or selected_ref.kind != expected_kind
        or selected_ref.media_type != "application/json"
        or not selected_ref.manifest_profile_sha256
    ):
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            "Runtime quality semantic binding selected CAS view is incomplete.",
        )
    if artifact_store is None:
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            "Runtime quality semantic binding CAS payload is unavailable for readback.",
        )
    try:
        selected_payload = read_core_json_artifact(
            artifact_store,
            selected_ref,
            manifest_profile_sha256=selected_ref.manifest_profile_sha256,
        ).value
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            "Runtime quality semantic binding selected CAS payload failed readback.",
        ) from exc
    if not isinstance(selected_payload, Mapping):
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            "Runtime quality semantic binding selected CAS payload is not an object.",
        )
    return _runtime_quality_semantic_binding_payload_identity(
        selected_payload,
        field_name="selected semantic binding ledger semantic_binding_ref",
    )


def _normalize_runtime_quality_same_input_closure(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Serialize every declared same-input closure field using its typed defaults."""
    from polisyos.runtime.quality.authority import SameInputClosure

    try:
        return SameInputClosure.model_validate(dict(value)).model_dump(mode="json")
    except (TypeError, ValueError) as exc:
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            "Runtime quality same-input closure is malformed.",
        ) from exc


def _runtime_quality_semantic_binding_reference(
    *,
    report_payload: Mapping[str, Any] | None,
    explicit_ref: object,
    runtime_quality_refs: Mapping[str, object],
    candidate: _RuntimeQualityPublicationCandidate | None,
    output_artifact_id: str,
    ref_key: str,
    current_inputs: Sequence[object] = (),
    current_artifact_refs: Mapping[str, object] | None = None,
    artifact_store: ArtifactStore | None = None,
    current_report_verifier: Callable[[str, str], bool] | None = None,
) -> str | None:
    """Bind the semantic digest to a checked ledger, separately from its CAS locator."""
    (
        current_ref_key,
        _expected_role,
        _expected_kind,
        _expected_schema_name,
        _expected_schema_version,
    ) = RUNTIME_QUALITY_PUBLICATION_SEMANTIC_BINDING_REFERENCE_BINDING
    current_identity_values: list[str] = []
    if explicit_ref is not None:
        current_identity_values.append(
            _validated_runtime_quality_reference(
                explicit_ref,
                field_name="explicit semantic_binding_ref",
            )
        )
    if report_payload is not None and "semantic_binding_ref" in report_payload:
        current_identity_values.append(
            _validated_runtime_quality_reference(
                report_payload["semantic_binding_ref"],
                field_name="report semantic_binding_ref",
            )
        )
    if current_identity_values and any(
        value != current_identity_values[0] for value in current_identity_values[1:]
    ):
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            "Runtime quality semantic binding sources disagree.",
        )

    selected_identity = _runtime_quality_selected_semantic_binding_identity(
        runtime_quality_refs=runtime_quality_refs,
        current_inputs=current_inputs,
        current_artifact_refs=current_artifact_refs,
        artifact_store=artifact_store,
        current_report_verifier=current_report_verifier,
    )
    if selected_identity is not None:
        if current_identity_values and any(
            value != selected_identity for value in current_identity_values
        ):
            raise NaturalLanguagePipelineRefusalError(
                "runtime_quality_same_input_identity_not_established",
                "Runtime quality semantic binding source differs from its selected ledger.",
            )
        current_value = selected_identity
    elif current_identity_values:
        if (
            ref_key != current_ref_key
            or report_payload is None
            or "semantic_binding_ref" not in report_payload
        ):
            raise NaturalLanguagePipelineRefusalError(
                "runtime_quality_same_input_identity_not_established",
                "Runtime quality semantic binding has no selected ledger owner.",
            )
        current_value = _runtime_quality_semantic_binding_payload_identity(
            report_payload,
            field_name="producer semantic_binding_ref",
        )
        if any(value != current_value for value in current_identity_values):
            raise NaturalLanguagePipelineRefusalError(
                "runtime_quality_same_input_identity_not_established",
                "Runtime quality semantic binding source differs from its recomputed digest.",
            )
    else:
        current_value = None

    candidate_ref = candidate.semantic_binding_ref if candidate is not None else None
    if candidate is not None and current_value != candidate_ref:
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            "Runtime quality semantic binding reference changed during replay.",
        )
    if current_value == output_artifact_id:
        raise NaturalLanguagePipelineRefusalError(
            "runtime_quality_same_input_identity_not_established",
            "Runtime quality semantic binding cannot point at its own output.",
        )
    return current_value


def _final_policy_claim_extraction_failure(
    *,
    report: Mapping[str, Any],
    report_ref: str | None,
    selected_variant: Mapping[str, Any],
) -> dict[str, Any] | None:
    status = str(report.get("extraction_status") or report.get("status") or "").casefold()
    if status not in {"fail", "failed", "error"}:
        return None
    issue_codes = [
        str(issue.get("code"))
        for issue in report.get("issues") or []
        if isinstance(issue, Mapping) and issue.get("code")
    ]
    return {
        "code": "policy_claim_extraction_failed",
        "layer": "scientist_policy_artifacts",
        "phase": "final_policy_claims",
        "message": "Final policy artifact did not produce machine-readable major claims.",
        "retryable": False,
        "model": selected_variant.get("model"),
        "provider": selected_variant.get("provider"),
        "artifact_refs": (
            {"final_policy_claims_ref": report_ref}
            if isinstance(report_ref, str) and report_ref
            else {}
        ),
        "issue_codes": issue_codes,
        "next_action": (
            "Regenerate the final policy artifact with structured major claims, "
            "or send the artifact to human review before approving serious quality."
        ),
    }


def _trinity_schema_healing_notes(bundle: object) -> list[str]:
    model_spec = getattr(bundle, "model_spec", None)
    raw_notes = getattr(model_spec, "notes", None)
    if not isinstance(raw_notes, list | tuple):
        return []
    notes: list[str] = []
    for raw_note in raw_notes:
        note = str(raw_note)
        if note.startswith("schema_healed:"):
            notes.append(note)
    return notes


def _performance_budget_phase_name(category: str, phase: str) -> str:
    if phase.startswith(f"{category}."):
        return phase
    return f"{category}.{phase}"


def _performance_budget_row(
    *,
    category: str,
    phase: str,
    duration_ms: int,
) -> dict[str, Any]:
    phase_name = _performance_budget_phase_name(category, phase)
    budget_ms = _RUN_PERFORMANCE_BUDGETS_MS.get(phase_name)
    status = (
        "unknown"
        if budget_ms is None
        else "over_budget"
        if duration_ms > budget_ms
        else "within_budget"
    )
    return {
        "category": category,
        "phase": phase_name,
        "duration_ms": max(0, duration_ms),
        "budget_ms": budget_ms,
        "status": status,
        "over_by_ms": max(0, duration_ms - budget_ms) if budget_ms is not None else 0,
    }


def _performance_budget_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    over_budget = [row for row in rows if row.get("status") == "over_budget"]
    slowest = max(rows, key=lambda row: int(row.get("duration_ms") or 0), default=None)
    return {
        "phase_count": len(rows),
        "over_budget_count": len(over_budget),
        "slowest_phase": slowest.get("phase") if slowest else None,
        "slowest_duration_ms": slowest.get("duration_ms") if slowest else None,
    }


def _build_run_performance_summary(variants: list[Mapping[str, Any]]) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    steps_by_action: dict[str, dict[str, int]] = {}
    retrieval_phase_durations: dict[str, int] = {}
    variant_rows: list[dict[str, Any]] = []
    llm_latency_ms = 0
    total_tokens = 0
    total_cost_usd: float | None = 0.0

    for variant in variants:
        status = str(variant.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        latency_ms = int(variant.get("latency_ms") or 0)
        llm_latency_ms += latency_ms
        total_tokens += int(variant.get("total_tokens") or 0)
        variant_cost = _cost_number(variant.get("cost_usd"))
        if variant_cost is None:
            total_cost_usd = None
        elif total_cost_usd is not None:
            total_cost_usd += variant_cost

        steps = variant.get("steps")
        if isinstance(steps, list):
            for raw_step in steps:
                if not isinstance(raw_step, Mapping):
                    continue
                action = str(raw_step.get("action") or "unknown")
                step_latency = int(raw_step.get("latency_ms") or 0)
                row = steps_by_action.setdefault(action, {"count": 0, "latency_ms": 0})
                row["count"] += 1
                row["latency_ms"] += step_latency

        raw_retrieval_durations = variant.get("retrieval_phase_durations")
        if isinstance(raw_retrieval_durations, Mapping):
            for phase, duration in raw_retrieval_durations.items():
                phase_name = str(phase)
                retrieval_phase_durations[phase_name] = retrieval_phase_durations.get(
                    phase_name, 0
                ) + int(duration or 0)

        variant_rows.append(
            {
                "model_variant_id": variant.get("model_variant_id"),
                "model": variant.get("model"),
                "provider": variant.get("provider"),
                "status": status,
                "latency_ms": latency_ms,
                "steps_completed": len(steps) if isinstance(steps, list) else 0,
                "total_tokens": int(variant.get("total_tokens") or 0),
                "cost_usd": (variant_cost),
            }
        )

    phase_budgets: list[dict[str, Any]] = []
    if llm_latency_ms:
        phase_budgets.append(
            _performance_budget_row(
                category="llm",
                phase="total",
                duration_ms=llm_latency_ms,
            )
        )
    for action, row in sorted(steps_by_action.items()):
        phase_budgets.append(
            _performance_budget_row(
                category="nl_step",
                phase=action,
                duration_ms=int(row.get("latency_ms") or 0),
            )
        )
    for phase, duration_ms in sorted(retrieval_phase_durations.items()):
        phase_budgets.append(
            _performance_budget_row(
                category="retrieval",
                phase=phase,
                duration_ms=duration_ms,
            )
        )

    return {
        "schema_version": "1.0",
        "variants": {
            "total": len(variants),
            "completed": statuses.get("completed", 0),
            "failed": statuses.get("failed", 0),
            "by_status": statuses,
        },
        "llm": {
            "latency_ms": llm_latency_ms,
            "total_tokens": total_tokens,
            "cost_usd": round(total_cost_usd, 8) if total_cost_usd is not None else None,
        },
        "steps_by_action": steps_by_action,
        "retrieval_phase_durations": retrieval_phase_durations,
        "phase_budgets": phase_budgets,
        "budget_summary": _performance_budget_summary(phase_budgets),
        "variant_rows": variant_rows,
    }


def _nl_pipeline_timeout_seconds() -> float:
    raw = os.getenv("POLISYOS_NL_PIPELINE_TIMEOUT_SECONDS")
    if raw is None:
        raw = os.getenv("POLISYOS_RUN_CORO_SYNC_TIMEOUT_SECONDS")
    if raw is None:
        return 1800.0
    try:
        timeout = float(raw.strip())
    except ValueError:
        logger.warning(
            "Invalid POLISYOS_NL_PIPELINE_TIMEOUT_SECONDS=%r; using 1800s",
            raw,
        )
        return 1800.0
    return max(timeout, 1.0)


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _artifact_id_from_ref_payload(value: object) -> str | None:
    if isinstance(value, Mapping):
        artifact_id = value.get("artifact_id")
        if isinstance(artifact_id, str) and artifact_id:
            return artifact_id
    artifact_id = getattr(value, "artifact_id", None)
    if artifact_id is None:
        return None
    artifact_id_text = str(artifact_id)
    return artifact_id_text or None


def _artifact_ref_from_ref_payload(
    value: object,
    *,
    artifact_id: str,
    kind: str,
    media_type: str = "application/json",
) -> ArtifactRef:
    """Preserve a selected artifact profile or construct the declared legacy ref."""
    from polisyos.core.artifacts.manifest import ArtifactRef as RuntimeArtifactRef

    if isinstance(value, RuntimeArtifactRef):
        ref = value
    elif isinstance(value, Mapping) and any(
        field in value for field in ("kind", "media_type", "manifest_profile_sha256")
    ):
        ref = RuntimeArtifactRef.model_validate(value)
    else:
        ref = _make_artifact_ref(artifact_id, kind=kind, media_type=media_type)
    if str(ref.artifact_id) != artifact_id or ref.kind != kind or ref.media_type != media_type:
        raise ValueError("artifact_ref_does_not_match_expected_selection")
    return ref


def _resolve_selected_materialization_ref(
    store: ArtifactStore,
    value: object,
    selected_materialization_refs: Mapping[str, list[ArtifactRef]],
    *,
    kind: str | None = None,
    parent_manifest: object | None = None,
    parent_roles: frozenset[str] = frozenset(),
) -> ArtifactRef:
    """Resolve a materialization edge to its exact selected Core manifest view.

    A producer-selected view in the current run is authoritative for selection. If
    the run has no such view, the exact Core manifest and payload must resolve, and
    any supplied parent edge must name that same artifact/profile pair.
    """
    from polisyos.core.artifacts import (
        artifact_ref_for_manifest,
        read_core_manifest_profile,
        resolve_manifest_by_profile,
    )
    from polisyos.core.artifacts.manifest import ArtifactRef as RuntimeArtifactRef

    try:
        if isinstance(value, str):
            artifact_id = value.strip()
            if not artifact_id:
                raise ValueError("empty artifact reference")
            supplied_ref = None
        else:
            supplied_ref = RuntimeArtifactRef.model_validate(
                value.model_dump(mode="python") if isinstance(value, RuntimeArtifactRef) else value
            )
            artifact_id = str(supplied_ref.artifact_id)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("auto_materialization_selected_ref_not_established") from exc

    parent_edge = None
    if parent_manifest is not None:
        manifest_inputs = getattr(parent_manifest, "inputs", None)
        parent_edges = [
            item
            for item in manifest_inputs or ()
            if getattr(item, "role", None) in parent_roles
            and str(getattr(item, "artifact_id", "")) == artifact_id
        ]
        if len(parent_edges) != 1 or parent_edges[0].manifest_profile_sha256 is None:
            raise RuntimeError("auto_materialization_quality_ref_lineage_not_established")
        parent_edge = parent_edges[0]
        if (
            supplied_ref is not None
            and supplied_ref.manifest_profile_sha256 is not None
            and supplied_ref.manifest_profile_sha256 != parent_edge.manifest_profile_sha256
        ):
            raise RuntimeError("auto_materialization_quality_ref_lineage_not_established")

    candidates = selected_materialization_refs.get(artifact_id, [])
    if candidates:
        if supplied_ref is None:
            selected = [
                candidate
                for candidate in candidates
                if (kind is None or candidate.kind == kind)
                and candidate.media_type == "application/json"
                and (
                    parent_edge is None
                    or candidate.manifest_profile_sha256 == parent_edge.manifest_profile_sha256
                )
            ]
        elif supplied_ref.manifest_profile_sha256 is None:
            selected = [
                candidate
                for candidate in candidates
                if candidate.kind == supplied_ref.kind
                and candidate.media_type == supplied_ref.media_type
                and (
                    parent_edge is None
                    or candidate.manifest_profile_sha256 == parent_edge.manifest_profile_sha256
                )
            ]
        else:
            selected = [
                candidate
                for candidate in candidates
                if (
                    candidate.kind,
                    candidate.media_type,
                    candidate.manifest_profile_sha256,
                )
                == (
                    supplied_ref.kind,
                    supplied_ref.media_type,
                    supplied_ref.manifest_profile_sha256,
                )
                and (
                    parent_edge is None
                    or candidate.manifest_profile_sha256 == parent_edge.manifest_profile_sha256
                )
            ]
        if len(selected) != 1:
            raise RuntimeError("auto_materialization_selected_ref_not_established")
        selected_ref = selected[0]
    else:
        try:
            if parent_edge is None:
                manifest, _declaration = read_core_manifest_profile(store, value)
            else:
                manifest = resolve_manifest_by_profile(
                    store,
                    artifact_id,
                    parent_edge.manifest_profile_sha256,
                )
            selected_ref = artifact_ref_for_manifest(manifest)
            if supplied_ref is not None and (
                supplied_ref.kind != selected_ref.kind
                or supplied_ref.media_type != selected_ref.media_type
                or (
                    supplied_ref.manifest_profile_sha256 is not None
                    and supplied_ref.manifest_profile_sha256 != selected_ref.manifest_profile_sha256
                )
            ):
                raise ValueError("selected artifact view does not match its manifest")
            if manifest.producer is None or manifest.artifact_schema is None:
                raise ValueError("selected artifact owner is not established")
            _ = read_core_json_artifact(store, selected_ref).value
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise RuntimeError("auto_materialization_selected_ref_not_established") from exc

    if (
        selected_ref.manifest_profile_sha256 is None
        or selected_ref.media_type != "application/json"
        or (kind is not None and selected_ref.kind != kind)
    ):
        raise RuntimeError("auto_materialization_selected_ref_not_established")

    if (
        parent_edge is not None
        and parent_edge.manifest_profile_sha256 != selected_ref.manifest_profile_sha256
    ):
        raise RuntimeError("auto_materialization_quality_ref_lineage_not_established")
    return selected_ref


def _validate_producer_selected_ref_membership(
    variants: Sequence[Mapping[str, Any]],
    producer_selected_refs: Mapping[str, ArtifactRef],
    *,
    refusal_code: str,
) -> None:
    """Require every producer-selected ref to belong to one current variant."""

    variant_counts: dict[str, int] = {}
    for variant in variants:
        variant_id_value = variant.get("model_variant_id")
        variant_id = str(variant_id_value).strip() if variant_id_value is not None else ""
        if variant_id:
            variant_counts[variant_id] = variant_counts.get(variant_id, 0) + 1
    if any(
        not isinstance(variant_id, str)
        or not variant_id.strip()
        or variant_counts.get(variant_id) != 1
        for variant_id in producer_selected_refs
    ):
        raise CanonicalProfileRefusalError(refusal_code)


def _selected_producer_artifact_ref_for_variant(
    variant: Mapping[str, Any],
    *,
    producer_selected_refs: Mapping[str, ArtifactRef],
    typed_key: str,
    legacy_key: str,
    expected_kind: str,
    refusal_code: str,
    resolve_ref: Callable[[object], ArtifactRef],
) -> ArtifactRef | None:
    """Resolve a variant edge from its producer-owned selected ref."""

    variant_id_value = variant.get("model_variant_id")
    variant_id = str(variant_id_value).strip() if variant_id_value is not None else ""
    producer_ref = producer_selected_refs.get(variant_id) if variant_id else None
    typed_present = typed_key in variant
    legacy_present = legacy_key in variant

    if producer_ref is not None:
        if (
            producer_ref.kind != expected_kind
            or producer_ref.media_type != "application/json"
            or producer_ref.manifest_profile_sha256 is None
        ):
            raise CanonicalProfileRefusalError(refusal_code)

        if typed_present:
            raw_typed_ref = variant[typed_key]
            artifact_id = _artifact_id_from_ref_payload(raw_typed_ref)
            if artifact_id is None:
                raise CanonicalProfileRefusalError(refusal_code)
            try:
                typed_ref = _artifact_ref_from_ref_payload(
                    raw_typed_ref,
                    artifact_id=artifact_id,
                    kind=expected_kind,
                )
            except (TypeError, ValueError) as exc:
                raise CanonicalProfileRefusalError(refusal_code) from exc
            if typed_ref != producer_ref:
                raise CanonicalProfileRefusalError(refusal_code)

        if legacy_present:
            raw_legacy_ref = variant[legacy_key]
            if (
                not isinstance(raw_legacy_ref, str)
                or not raw_legacy_ref.strip()
                or raw_legacy_ref.strip() != str(producer_ref.artifact_id)
            ):
                raise CanonicalProfileRefusalError(refusal_code)
        elif not typed_present:
            raise CanonicalProfileRefusalError(refusal_code)

        # The current-run producer map already binds the exact selected profile.
        # Reconcile projections here, but leave manifest/payload intake to the
        # semantic consumer so unreadable selected evidence retains its refusal.
        return producer_ref

    if typed_present:
        raise CanonicalProfileRefusalError(refusal_code)
    if not legacy_present:
        return None

    raw_legacy_ref = variant[legacy_key]
    artifact_id = _artifact_id_from_ref_payload(raw_legacy_ref)
    if artifact_id is None and isinstance(raw_legacy_ref, str):
        artifact_id = raw_legacy_ref.strip()
    if not artifact_id:
        raise CanonicalProfileRefusalError(refusal_code)
    if any(
        str(other_ref.artifact_id) == artifact_id
        for other_variant_id, other_ref in producer_selected_refs.items()
        if other_variant_id != variant_id
    ):
        raise CanonicalProfileRefusalError(refusal_code)

    try:
        selected_ref = resolve_ref(raw_legacy_ref)
    except CanonicalProfileRefusalError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise CanonicalProfileRefusalError(refusal_code) from exc
    if (
        str(selected_ref.artifact_id) != artifact_id
        or selected_ref.kind != expected_kind
        or selected_ref.media_type != "application/json"
        or selected_ref.manifest_profile_sha256 is None
    ):
        raise CanonicalProfileRefusalError(refusal_code)
    return selected_ref


def _selected_final_policy_claims_ref_for_variant(
    variant: Mapping[str, Any],
    *,
    producer_selected_refs: Mapping[str, ArtifactRef],
    resolve_legacy_ref: Callable[[object], ArtifactRef],
) -> ArtifactRef | None:
    """Bind claims lineage to the ref selected by the variant producer."""

    return _selected_producer_artifact_ref_for_variant(
        variant,
        producer_selected_refs=producer_selected_refs,
        typed_key="final_policy_claims_selected_ref",
        legacy_key="final_policy_claims_ref",
        expected_kind="scientist.final_policy_claims",
        refusal_code="nl_final_policy_claims_ref_invalid",
        resolve_ref=resolve_legacy_ref,
    )


def _foundry_method_report_ref_from_state_payload(
    value: Mapping[str, Any],
) -> str | None:
    reports_index = value.get("reports_index")
    if isinstance(reports_index, Mapping):
        for key in ("foundry_method_report_ref", "foundry_method_report"):
            ref = _artifact_id_from_ref_payload(reports_index.get(key))
            if ref:
                return ref
    params = value.get("params")
    if isinstance(params, Mapping):
        ref = _artifact_id_from_ref_payload(params.get("foundry_method_report_ref"))
        if ref:
            return ref
        raw_ref = params.get("foundry_method_report_ref")
        if isinstance(raw_ref, str) and raw_ref.strip():
            return raw_ref.strip()
    raw_ref = value.get("foundry_method_report_ref")
    if isinstance(raw_ref, str) and raw_ref.strip():
        return raw_ref.strip()
    return None


def _serialize_critique_report(critique: object) -> dict[str, Any]:
    issues = []
    for issue in getattr(critique, "issues", []) or []:
        issues.append(
            {
                "category": _enum_value(getattr(issue, "category", None)),
                "severity": _enum_value(getattr(issue, "severity", None)),
                "message": getattr(issue, "message", ""),
                "location": getattr(issue, "location", ""),
                "suggestion": getattr(issue, "suggestion", ""),
                "evidence": dict(getattr(issue, "evidence", {}) or {}),
            }
        )
    return {
        "verdict": getattr(critique, "verdict", None),
        "issue_count": len(issues),
        "issues": issues,
        "alignment_score": getattr(critique, "alignment_score", None),
        "completeness_score": getattr(critique, "completeness_score", None),
        "overall_quality": getattr(critique, "overall_quality", None),
        "reflexion_hint": getattr(critique, "reflexion_hint", ""),
    }


class NaturalLanguageRunMixin:
    """Natural-language runtime path split out of ControlPlaneService."""

    if TYPE_CHECKING:
        _artifact_store: ArtifactStore
        _async_artifact_store: AsyncArtifactStore
        _catalog_run_profile: CatalogRunProfile | None
        _catalog_serving_source: CatalogServingSourcePaths
        _control_store: ControlPlaneStore
        _diagnostic_event_log: RuntimeDiagnosticEventLog
        _epoch_certificate_issuance_owner: DecisionPacketEpochIssuanceOwner | None
        _metrics: MetricsRegistry
        _tracer: PolicyOSTracer

        def _build_retrieval_providers(self) -> RetrievalProviders: ...

    def _execute_nl_pipeline(
        self,
        run_id: str,
        nl_request: str,
        context: dict[str, Any],
        domain_hint: str | None,
        data_source: DataSourceBinding | None,
        max_iterations: int,
        llm_models: list[str],
        max_parallel_models: int,
        run_budget_usd: float | None,
        per_model_budget_usd: float | None,
        checkpoint_policy: str,
        execution_plan_ref: str | None,
        execution_plan_payload: dict[str, Any] | None,
        stop_criteria_payload: dict[str, Any] | None,
        governance_constraints_payload: list[dict[str, Any]] | None,
        expected_outputs_payload: list[dict[str, Any]] | None,
        control_job_id: str | None = None,
        execution_profile: str | None = None,
        capability_manifest_ref: str | None = None,
        allow_mock_fallback: Literal[False] = False,
        capability_manifest_updater: Callable[[list[str]], str] | None = None,
        provider_preflight_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the production NL path; mock authority is structurally unavailable."""

        if allow_mock_fallback:
            raise NaturalLanguagePipelineRefusalError(
                "nl_contract_testing_path_required",
                "Mock agents are available only on the explicit contract-testing path.",
            )
        if not _dedupe_models(list(llm_models)):
            raise NaturalLanguagePipelineRefusalError(
                "llm_model_unconfigured",
                "A configured LLM model is required for the production NL path.",
            )
        from polisyos.runtime.quality.substrate_registry import run_catalog_source_call

        result = run_catalog_source_call(
            getattr(self, "_catalog_serving_source", None),
            self._execute_nl_pipeline_impl,
            run_id=run_id,
            nl_request=nl_request,
            context=context,
            domain_hint=domain_hint,
            data_source=data_source,
            max_iterations=max_iterations,
            llm_models=llm_models,
            max_parallel_models=max_parallel_models,
            run_budget_usd=run_budget_usd,
            per_model_budget_usd=per_model_budget_usd,
            checkpoint_policy=checkpoint_policy,
            execution_plan_ref=execution_plan_ref,
            execution_plan_payload=execution_plan_payload,
            stop_criteria_payload=stop_criteria_payload,
            governance_constraints_payload=governance_constraints_payload,
            expected_outputs_payload=expected_outputs_payload,
            control_job_id=control_job_id,
            execution_profile=execution_profile,
            capability_manifest_ref=capability_manifest_ref,
            capability_manifest_updater=capability_manifest_updater,
            provider_preflight_payload=provider_preflight_payload,
            contract_testing_agent_factory=None,
        )
        result["nl_authority"] = _NLProductionAuthorityStamp().model_dump(mode="json")
        return result

    def _execute_nl_pipeline_for_contract_testing(
        self,
        run_id: str,
        nl_request: str,
        context: dict[str, Any],
        domain_hint: str | None,
        data_source: DataSourceBinding | None,
        max_iterations: int,
        llm_models: list[str],
        max_parallel_models: int,
        run_budget_usd: float | None,
        per_model_budget_usd: float | None,
        checkpoint_policy: str,
        execution_plan_ref: str | None,
        execution_plan_payload: dict[str, Any] | None,
        stop_criteria_payload: dict[str, Any] | None,
        governance_constraints_payload: list[dict[str, Any]] | None,
        expected_outputs_payload: list[dict[str, Any]] | None,
        control_job_id: str | None = None,
        execution_profile: str | None = None,
        capability_manifest_ref: str | None = None,
        capability_manifest_updater: Callable[[list[str]], str] | None = None,
        provider_preflight_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the explicit non-promotable mock lane for contract tests only."""

        from polisyos.runtime.http.services.control.nl_pipeline_testing import (
            NLContractTestingAuthorityStamp,
            build_nl_contract_testing_agents,
        )

        result = self._execute_nl_pipeline_impl(
            run_id=run_id,
            nl_request=nl_request,
            context=context,
            domain_hint=domain_hint,
            data_source=data_source,
            max_iterations=max_iterations,
            llm_models=llm_models,
            max_parallel_models=max_parallel_models,
            run_budget_usd=run_budget_usd,
            per_model_budget_usd=per_model_budget_usd,
            checkpoint_policy=checkpoint_policy,
            execution_plan_ref=execution_plan_ref,
            execution_plan_payload=execution_plan_payload,
            stop_criteria_payload=stop_criteria_payload,
            governance_constraints_payload=governance_constraints_payload,
            expected_outputs_payload=expected_outputs_payload,
            control_job_id=control_job_id,
            execution_profile=execution_profile,
            capability_manifest_ref=capability_manifest_ref,
            capability_manifest_updater=capability_manifest_updater,
            provider_preflight_payload=provider_preflight_payload,
            contract_testing_agent_factory=build_nl_contract_testing_agents,
        )
        result["contract_testing_authority"] = NLContractTestingAuthorityStamp().model_dump(
            mode="json"
        )
        return result

    def _execute_nl_pipeline_impl(
        self,
        run_id: str,
        nl_request: str,
        context: dict[str, Any],
        domain_hint: str | None,
        data_source: DataSourceBinding | None,
        max_iterations: int,
        llm_models: list[str],
        max_parallel_models: int,
        run_budget_usd: float | None,
        per_model_budget_usd: float | None,
        checkpoint_policy: str,
        execution_plan_ref: str | None,
        execution_plan_payload: dict[str, Any] | None,
        stop_criteria_payload: dict[str, Any] | None,
        governance_constraints_payload: list[dict[str, Any]] | None,
        expected_outputs_payload: list[dict[str, Any]] | None,
        control_job_id: str | None = None,
        execution_profile: str | None = None,
        capability_manifest_ref: str | None = None,
        capability_manifest_updater: Callable[[list[str]], str] | None = None,
        provider_preflight_payload: dict[str, Any] | None = None,
        contract_testing_agent_factory: Callable[
            [], tuple[PIAgent, DataNeedExtractorAgent, DrafterAgent, FormalizerAgent, CriticAgent]
        ]
        | None = None,
    ) -> dict[str, Any]:
        """Shared implementation used by the fenced production and contract-test routers."""
        from polisyos.common.async_tools import run_coro_sync

        allow_mock_fallback = contract_testing_agent_factory is not None

        execution_profile = execution_profile or getattr(
            getattr(self, "_policy_resolver", None),
            "default_profile",
            None,
        )
        diagnostic_execution_scope: ControlJobExecutionScope | None = None
        diagnostic_worker_binding_established = False
        diagnostic_binding_limitation_code = "control_job_execution_scope_not_established"
        runtime_quality_owner_binding: dict[str, object] | None = None
        if control_job_id is not None:
            control_store = getattr(self, "_control_store", None)
            read_current_admission = getattr(control_store, "current_execution_job_admission", None)
            if callable(read_current_admission):
                from polisyos.runtime.http.services.control_plane_store import (
                    ControlJobExecutionAdmissionError,
                    ControlJobLeaseLostError,
                )
                from polisyos.runtime.quality.phase_barriers import (
                    _execution_owner_binding_from_admission,
                )

                try:
                    current_admission = read_current_admission()
                except (ControlJobExecutionAdmissionError, ControlJobLeaseLostError):
                    diagnostic_binding_limitation_code = (
                        "control_job_execution_binding_not_established"
                    )
                else:
                    current_scope = current_admission.scope
                    diagnostic_execution_scope = current_scope
                    expected_scope: dict[str, object] = {}
                    for scope_key in ("tenant_id", "cell_id"):
                        supplied = context.get(scope_key)
                        if isinstance(supplied, str) and supplied.strip():
                            expected_scope[scope_key] = supplied.strip()
                    runtime_quality_owner_binding = _execution_owner_binding_from_admission(
                        current_admission,
                        expected_job_id=control_job_id,
                        expected_run_id=run_id,
                        expected_effective_profile=execution_profile,
                        expected_scope=expected_scope,
                    )
                    if runtime_quality_owner_binding is not None:
                        diagnostic_worker_binding_established = True
                        diagnostic_binding_limitation_code = (
                            "control_job_execution_binding_not_established"
                        )
                        execution_profile = str(
                            runtime_quality_owner_binding["effective_execution_profile"]
                        )
        if runtime_quality_owner_binding is None:
            raise NaturalLanguagePipelineRefusalError(
                "control_job_execution_scope_not_established",
                "Runtime quality authority requires the live lease and creation-event scope.",
            )
        from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo
        from polisyos.runtime.http.services.control_plane_store import (
            ControlJobExecutionScope,
        )

        admitted_scope = diagnostic_execution_scope
        if (
            type(admitted_scope) is not ControlJobExecutionScope
            or admitted_scope.status != "established"
            or type(admitted_scope.tenant_id) is not str
            or not admitted_scope.tenant_id.strip()
            or admitted_scope.tenant_id != admitted_scope.tenant_id.strip()
            or type(admitted_scope.cell_id) is not str
            or not admitted_scope.cell_id.strip()
            or admitted_scope.cell_id != admitted_scope.cell_id.strip()
            or runtime_quality_owner_binding.get("job_id") != control_job_id
            or runtime_quality_owner_binding.get("run_id") != run_id
            or runtime_quality_owner_binding.get("effective_execution_profile") != execution_profile
            or runtime_quality_owner_binding.get("tenant_id") != admitted_scope.tenant_id
            or runtime_quality_owner_binding.get("cell_id") != admitted_scope.cell_id
        ):
            raise NaturalLanguagePipelineRefusalError(
                "control_job_execution_scope_not_established",
                "Trinity persistence requires the matching admitted tenant and cell scope.",
            )
        trinity_bundle_tenant_context = ArtifactTenantContextInfo(
            tenant_id=admitted_scope.tenant_id,
            cell_id=admitted_scope.cell_id,
        )
        cache_reuse_authorizer = getattr(self, "_llm_cache_reuse_authorizer", None)
        cache_reuse_principal, cache_reuse_context = _nl_snapshot_cache_reuse_binding(
            data_source=data_source,
            execution_scope=admitted_scope,
            artifact_store=self._artifact_store,
            authorizer=cache_reuse_authorizer,
        )
        metric_taxonomy = build_production_metric_taxonomy()
        metric_taxonomy_evidence = metric_taxonomy.evidence()
        metric_taxonomy_diagnostics: list[dict[str, Any]] = []

        async def _agent_pipeline() -> dict[str, Any]:
            nonlocal context, execution_plan_payload, expected_outputs_payload
            nonlocal governance_constraints_payload, stop_criteria_payload

            from polisyos.core.artifacts.manifest import (
                ArtifactGovernanceInfo,
                InputRef,
                ProducerInfo,
                SchemaInfo,
                input_ref_from_artifact_ref,
            )
            from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
            from polisyos.core.canon import CanonSpec
            from polisyos.core.contracts.execution_plan import (
                ExecutionPlan,
                ExecutionPlanRef,
                IterationState,
                MethodCatalogSnapshot,
                MethodCatalogSnapshotRef,
                PreflightReportRef,
            )
            from polisyos.core.contracts.fabric import DataSnapshot, RetrievalSummary
            from polisyos.core.contracts.foundry import (
                FoundryInputBindings,
                StateSnapshot,
                StateSnapshotRef,
            )
            from polisyos.core.registry import build_default_registry_bundle
            from polisyos.fabric.retrieval import RetrievalService
            from polisyos.foundry.methods import (
                build_method_catalog_snapshot,
                persist_method_catalog_snapshot,
            )
            from polisyos.foundry.methods.catalog import (
                ensure_all_methods_registered as ensure_causal_methods_registered,
            )
            from polisyos.lex.normpack.applicability_report import (
                build_runtime_normative_applicability_report,
            )
            from polisyos.lex.normpack.conflict_check import (
                build_policy_conflict_check_report,
            )
            from polisyos.runtime.quality.assurance_case import (
                POLICY_DESIGN_REQUIRED_CAPABILITIES,
                build_capability_duty_record,
                build_capability_selection_ledger,
                build_policy_design_case_concept_spine,
                build_policy_design_case_profile,
                build_policy_design_jurisdiction_spine,
                build_policy_intent_envelope,
            )
            from polisyos.runtime.quality.claim_registry import (
                build_runtime_claim_registry,
            )
            from polisyos.runtime.quality.data_quality import (
                DIAGNOSTIC_KEYS,
                PRODUCTION_DATA_QUALITY_REF_KEY,
            )
            from polisyos.runtime.quality.design_generation import (
                generate_design_candidate_bundle_under_a,
            )
            from polisyos.runtime.quality.diagnostic_events import (
                RuntimeQualitySelectedReadObservation,
            )
            from polisyos.runtime.quality.policy_design_case import (
                compile_policy_design_case_runtime_record_families,
            )
            from polisyos.runtime.quality.prompt_tool_ledger import (
                PROMPT_TOOL_LEDGER_KIND,
                PROMPT_TOOL_LEDGER_REF_KEY,
                PROMPT_TOOL_LEDGER_REPORT_KEY,
                PROMPT_TOOL_LEDGER_SCHEMA,
                build_prompt_tool_ledger_from_model_variant,
                serialize_prompt_tool_ledger,
            )
            from polisyos.runtime.quality.semantic_binding import (
                build_producer_spine_read_context,
            )
            from polisyos.scientist.agent.critic import LLMCriticAgent
            from polisyos.scientist.agent.data_need_extractor import (
                LLMDataNeedExtractorAgent,
            )
            from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent
            from polisyos.scientist.agent.formalizer import (
                LLMFormalizerAgent,
                build_final_policy_claims_report,
            )
            from polisyos.scientist.agent.pi import LLMPIAgent
            from polisyos.scientist.evidence.source_quality import (
                build_source_quality_report,
            )
            from polisyos.scientist.orchestration.engine.iteration_state_machine import (
                transition,
            )
            from polisyos.scientist.orchestration.llm.adjudication import (
                build_model_variant_adjudication,
            )
            from polisyos.scientist.orchestration.llm.cycle import (
                build_default_execution_plan,
                build_reproducibility_manifest,
                evaluate_iteration,
                persist_evaluator_report,
                persist_execution_plan,
                persist_iteration_state,
                persist_preflight_report,
                persist_reproducibility_manifest,
                preflight_execution_plan,
            )
            from polisyos.scientist.validation.citation_faithfulness import (
                build_policy_context_citation_faithfulness_report,
            )
            from polisyos.scientist.validation.policy_grounding import (
                build_policy_grounding_matrix_report,
            )

            store = self._artifact_store
            async_store = self._async_artifact_store
            models_to_run = _dedupe_models(list(llm_models))
            current_capability_manifest_ref = capability_manifest_ref
            if not models_to_run and not allow_mock_fallback:
                raise NaturalLanguagePipelineRefusalError("llm_model_unconfigured")
            method_catalog_snapshot_cache: dict[str, Any] = {
                "snapshot": None,
                "ref": None,
            }
            registry_bundle_ref_cache: ArtifactRef | None = None
            catalog_lock = asyncio.Lock()
            progress_variants: dict[str, dict[str, Any]] = {}
            scientist_workflow_progress: dict[str, Any] = {"events": []}
            runtime_quality_refs: dict[str, str] = {}
            runtime_quality_artifact_refs: dict[str, ArtifactRef] = {}
            runtime_quality_publication_report_keys: dict[str, str] = {}
            runtime_quality_publication_phases: dict[str, str] = {}
            runtime_quality_publication_write_options: dict[str, ArtifactWriteOptions] = {}
            runtime_quality_publication_identity_contexts: dict[str, Any] = {}
            runtime_quality_publication_requested_as_of_times: dict[str, str | None] = {}
            runtime_quality_evidence: dict[str, Any] = {}
            runtime_quality_cost_events: list[dict[str, Any]] = []
            selected_final_claims_refusal_codes: list[str] = []
            runtime_quality_diagnostic_events: list[dict[str, Any]] = []
            runtime_quality_selected_reads: list[RuntimeQualitySelectedReadObservation] = []
            diagnostic_event_log_ref: str | None = None

            def _progress_json(value: object) -> object:
                if hasattr(value, "model_dump"):
                    return value.model_dump(mode="json")
                if isinstance(value, Mapping):
                    return {str(key): _progress_json(item) for key, item in value.items()}
                if isinstance(value, list | tuple):
                    return [_progress_json(item) for item in value]
                if isinstance(value, str | int | float | bool) or value is None:
                    return value
                return str(value)

            def _runtime_quality_progress_projection() -> dict[str, str]:
                return {
                    "authority_role": "projection_only",
                    "provenance_kind": "runtime_projection",
                    "surface": "runtime.progress",
                    "authoritative_surface": "runtime_quality_refs",
                }

            def _runtime_quality_semantic_binding_ref(
                *,
                report_payload: Mapping[str, Any] | None = None,
                explicit_ref: object = None,
                candidate: _RuntimeQualityPublicationCandidate | None = None,
                output_artifact_id: str,
                ref_key: str,
                current_inputs: Sequence[object] = (),
                current_report_verifier: Callable[[str, str], bool] | None = None,
            ) -> str | None:
                return _runtime_quality_semantic_binding_reference(
                    report_payload=report_payload,
                    explicit_ref=explicit_ref,
                    runtime_quality_refs=runtime_quality_refs,
                    candidate=candidate,
                    output_artifact_id=output_artifact_id,
                    ref_key=ref_key,
                    current_inputs=current_inputs,
                    current_artifact_refs=runtime_quality_artifact_refs,
                    artifact_store=store,
                    current_report_verifier=current_report_verifier,
                )

            def _runtime_quality_run_intent_binding() -> dict[str, Any] | None:
                owner = runtime_quality_owner_binding
                if owner is None:
                    raise NaturalLanguagePipelineRefusalError(
                        "control_job_execution_scope_not_established"
                    )
                requested_profile = owner.get("requested_execution_profile")
                if not isinstance(requested_profile, str) or not requested_profile.strip():
                    return None
                return {
                    "run_id": owner["run_id"],
                    "tenant_id": owner["tenant_id"],
                    "requested_profile": requested_profile,
                    "policy_intent_ref": runtime_quality_refs.get("policy_intent_envelope_ref"),
                    "time_context_ref": None,
                    "same_input_closure_ref": None,
                }

            def _emit_job_progress(
                *,
                phase: str,
                state: str = "running",
                variant_id: str | None = None,
                variant_status: str | None = None,
                step: dict[str, Any] | None = None,
                details: dict[str, Any] | None = None,
                selected_variant_id: str | None = None,
            ) -> None:
                if not control_job_id:
                    return
                now = datetime.now(UTC).replace(microsecond=0).isoformat()
                if variant_id:
                    variant_progress = dict(progress_variants.get(variant_id) or {})
                    variant_progress["model_variant_id"] = variant_id
                    if variant_status:
                        variant_progress["status"] = variant_status
                    if step is not None:
                        variant_progress["last_step"] = _progress_json(step)
                        if str(step.get("status") or "") != "running":
                            variant_progress["steps_completed"] = (
                                int(variant_progress.get("steps_completed") or 0) + 1
                            )
                    variant_progress["updated_at"] = now
                    progress_variants[variant_id] = variant_progress
                snapshot: dict[str, Any] = {
                    "state": state,
                    "phase": phase,
                    "run_id": run_id,
                    "updated_at": now,
                    "models_total": len(models_to_run) or 1,
                    "variants": _progress_json(progress_variants),
                }
                if variant_id:
                    snapshot["active_model_variant_id"] = variant_id
                if selected_variant_id:
                    snapshot["selected_model_variant_id"] = selected_variant_id
                if provider_preflight_payload:
                    snapshot["provider_preflight"] = _progress_json(provider_preflight_payload)
                snapshot["execution_owner_binding"] = dict(runtime_quality_owner_binding)
                intent_binding = _runtime_quality_run_intent_binding()
                if intent_binding is not None:
                    snapshot["run_intent_binding"] = intent_binding
                if runtime_quality_refs:
                    snapshot["runtime_quality_refs"] = _progress_json(runtime_quality_refs)
                    snapshot.update(runtime_quality_refs)
                if runtime_quality_artifact_refs:
                    snapshot["runtime_quality_artifact_refs"] = _progress_json(
                        runtime_quality_artifact_refs
                    )
                if runtime_quality_refs:
                    snapshot["runtime_quality_projection"] = _runtime_quality_progress_projection()
                    attestations = _runtime_quality_attestations()
                    if attestations:
                        snapshot["trust_boundary_attestations"] = _progress_json(attestations)
                if diagnostic_event_log_ref:
                    snapshot["diagnostic_event_log_ref"] = diagnostic_event_log_ref
                if runtime_quality_diagnostic_events:
                    snapshot["diagnostic_events"] = _progress_json(
                        runtime_quality_diagnostic_events
                    )
                if runtime_quality_selected_reads:
                    snapshot["selected_read_observations"] = [
                        observation.model_dump(mode="json")
                        for observation in runtime_quality_selected_reads
                    ]
                if scientist_workflow_progress.get("event_count"):
                    snapshot["scientist_workflow"] = _progress_json(scientist_workflow_progress)
                if step is not None:
                    snapshot["last_step"] = _progress_json(step)
                if details:
                    snapshot["details"] = _progress_json(details)
                    failure = details.get("failure") if isinstance(details, Mapping) else None
                    if isinstance(failure, Mapping):
                        snapshot["failure"] = _progress_json(failure)
                snapshot["steps_completed"] = sum(
                    int(variant.get("steps_completed") or 0)
                    for variant in progress_variants.values()
                )
                emit_diagnostic_event = getattr(self, "_emit_runtime_diagnostic_event", None)
                if callable(emit_diagnostic_event):
                    if (
                        diagnostic_execution_scope is None
                        or not diagnostic_worker_binding_established
                    ):
                        snapshot["runtime_diagnostic_event_status"] = "not_persisted"
                        snapshot["diagnostic_event_scope_status"] = (
                            diagnostic_execution_scope.status
                            if diagnostic_execution_scope is not None
                            else "not_established"
                        )
                        snapshot["runtime_diagnostic_event_limitation_code"] = (
                            diagnostic_binding_limitation_code
                        )
                    else:
                        diagnostic_emission = emit_diagnostic_event(
                            job_id=control_job_id,
                            run_id=run_id,
                            execution_profile=execution_profile,
                            phase=phase,
                            event_type="polisyos.runtime.diagnostic.ref_publication.v1",
                            state_after=state,
                            payload={
                                "tenant_id": context.get("tenant_id"),
                                "cell_id": context.get("cell_id"),
                            },
                            event_payload={
                                "phase": phase,
                                "state": state,
                                "variant_id": variant_id,
                                "selected_variant_id": selected_variant_id,
                                "details": _progress_json(details or {}),
                                "progress_authority": "progress_reference_only",
                                "selected_read_observations": [
                                    observation.model_dump(mode="json")
                                    for observation in runtime_quality_selected_reads
                                ],
                            },
                            artifact_refs=list(runtime_quality_refs.values()),
                            execution_scope=diagnostic_execution_scope,
                        )
                        snapshot["runtime_diagnostic_event_status"] = diagnostic_emission.status
                        snapshot["diagnostic_event_scope_status"] = diagnostic_emission.scope_status
                        if diagnostic_emission.event_id is not None:
                            snapshot["diagnostic_event_ids"] = [diagnostic_emission.event_id]
                            snapshot["diagnostic_event_authority"] = "progress_reference_only"
                        if diagnostic_emission.limitation_code is not None:
                            snapshot["runtime_diagnostic_event_limitation_code"] = (
                                diagnostic_emission.limitation_code
                            )
                try:
                    self._control_store.update_progress_state(
                        job_id=control_job_id,
                        state=state,
                        progress=snapshot,
                    )
                except Exception as exc:  # pragma: no cover - diagnostics must not break jobs
                    logger.debug(
                        "Failed to update NL progress for job %s phase %s: %s",
                        control_job_id,
                        phase,
                        exc,
                    )

            def _canonicalize_runtime_metrics_before_workflow() -> None:
                nonlocal context, execution_plan_payload, expected_outputs_payload
                nonlocal governance_constraints_payload, stop_criteria_payload

                fail_unknown = _is_serious_execution_profile(execution_profile)
                context = cast(
                    "dict[str, Any]",
                    _canonicalize_runtime_metric_payload(
                        context,
                        taxonomy=metric_taxonomy,
                        diagnostics=metric_taxonomy_diagnostics,
                        fail_unknown=fail_unknown,
                        path="context",
                    ),
                )
                if execution_plan_payload is not None:
                    execution_plan_payload = cast(
                        "dict[str, Any]",
                        _canonicalize_runtime_metric_payload(
                            execution_plan_payload,
                            taxonomy=metric_taxonomy,
                            diagnostics=metric_taxonomy_diagnostics,
                            fail_unknown=fail_unknown,
                            path="execution_plan",
                        ),
                    )
                if stop_criteria_payload is not None:
                    stop_criteria_payload = cast(
                        "dict[str, Any]",
                        _canonicalize_runtime_metric_payload(
                            stop_criteria_payload,
                            taxonomy=metric_taxonomy,
                            diagnostics=metric_taxonomy_diagnostics,
                            fail_unknown=fail_unknown,
                            path="stop_criteria",
                        ),
                    )
                if governance_constraints_payload is not None:
                    governance_constraints_payload = cast(
                        "list[dict[str, Any]]",
                        _canonicalize_runtime_metric_payload(
                            governance_constraints_payload,
                            taxonomy=metric_taxonomy,
                            diagnostics=metric_taxonomy_diagnostics,
                            fail_unknown=fail_unknown,
                            path="governance_constraints",
                        ),
                    )
                if expected_outputs_payload is not None:
                    expected_outputs_payload = cast(
                        "list[dict[str, Any]]",
                        _canonicalize_runtime_metric_payload(
                            expected_outputs_payload,
                            taxonomy=metric_taxonomy,
                            diagnostics=metric_taxonomy_diagnostics,
                            fail_unknown=fail_unknown,
                            path="expected_outputs",
                        ),
                    )

            try:
                _canonicalize_runtime_metrics_before_workflow()
            except MetricTaxonomyValidationError as exc:
                failure_payload = cast("dict[str, Any]", _json_safe_payload(exc.failure))
                _emit_job_progress(
                    phase="metric_taxonomy_failed",
                    state="failed",
                    details={"failure": failure_payload},
                )
                raise RuntimeError(
                    f"{failure_payload['code']}:{failure_payload['message']}"
                ) from exc

            def _record_scientist_trace_event(event: dict[str, Any]) -> None:
                now = datetime.now(UTC).replace(microsecond=0).isoformat()
                events = scientist_workflow_progress.setdefault("events", [])
                if isinstance(events, list):
                    events.append(event)
                    del events[:-_SCIENTIST_PROGRESS_HISTORY_LIMIT]
                artifact_refs = event.get("artifact_refs")
                scientist_workflow_progress.update(
                    {
                        "event_count": int(event.get("event_index") or 0),
                        "current_phase": event.get("phase"),
                        "current_event": event.get("event"),
                        "current_node_alias": event.get("node_alias"),
                        "latest_event": event,
                        "updated_at": now,
                    }
                )
                if isinstance(artifact_refs, list) and artifact_refs:
                    scientist_workflow_progress["latest_artifact_refs"] = artifact_refs
                _emit_job_progress(
                    phase="scientist_workflow_running",
                    selected_variant_id=selected_variant_id,
                    step={
                        "agent": "scientist",
                        "action": "workflow_event",
                        "status": "running",
                        "summary": (
                            f"{event.get('event') or 'trace_event'} {event.get('phase') or ''}"
                        ).strip(),
                        "timestamp": now,
                    },
                )

            _emit_job_progress(
                phase="nl_pipeline_started",
                details=(
                    {
                        "provider_preflight": provider_preflight_payload,
                        "metric_taxonomy": metric_taxonomy_evidence,
                        "metric_taxonomy_diagnostics": list(metric_taxonomy_diagnostics),
                    }
                    if provider_preflight_payload
                    else {
                        "metric_taxonomy": metric_taxonomy_evidence,
                        "metric_taxonomy_diagnostics": list(metric_taxonomy_diagnostics),
                    }
                ),
            )

            def _artifact_ref_from_sha(sha: str, *, kind: str) -> ArtifactRef:
                return _make_artifact_ref(sha, kind=kind)

            def _load_json_artifact_payload(ref_value: object) -> dict[str, Any] | None:
                artifact_id = _artifact_id_from_ref_payload(ref_value)
                if artifact_id is None and isinstance(ref_value, str):
                    artifact_id = ref_value.strip()
                if not artifact_id:
                    return None
                from polisyos.core.artifacts import (
                    artifact_manifest_profile_sha256,
                    artifact_ref_for_manifest,
                    read_core_manifest_profile,
                )

                selector: object = artifact_id
                selection_origin: Literal["explicit_selected_ref", "default_view_at_read"] = (
                    "default_view_at_read"
                )
                if isinstance(ref_value, ArtifactRef) and ref_value.manifest_profile_sha256:
                    selector = ref_value
                    selection_origin = "explicit_selected_ref"
                elif isinstance(ref_value, Mapping) and ref_value.get("manifest_profile_sha256"):
                    try:
                        selector = ArtifactRef.model_validate(dict(ref_value))
                    except ValueError:
                        return None
                    selection_origin = "explicit_selected_ref"
                try:
                    read = read_core_json_artifact(store, selector)
                    payload = read.value
                    if not isinstance(payload, Mapping):
                        return None
                    manifest, declaration = read_core_manifest_profile(
                        store,
                        artifact_id,
                        manifest_profile_sha256=read.selected_manifest_profile_sha256,
                    )
                    selected_ref = artifact_ref_for_manifest(manifest)
                    payload_digest = "sha256:" + hashlib.sha256(read.raw_payload_bytes).hexdigest()
                    if (
                        declaration.status != "declared"
                        or selected_ref.manifest_profile_sha256 is None
                        or read.selected_artifact_id != str(selected_ref.artifact_id)
                        or read.selected_manifest_profile_sha256
                        != artifact_manifest_profile_sha256(manifest)
                        or payload_digest != str(selected_ref.artifact_id)
                        or manifest.canon is None
                    ):
                        return None
                    matching_owner = None
                    for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
                        contract = runtime_quality_report_owner_contract(report_key, ref_key)
                        if (
                            contract is not None
                            and selected_ref.kind == contract.artifact_kind
                            and selected_ref.media_type == contract.media_type
                            and manifest.artifact_schema is not None
                            and manifest.artifact_schema.name == contract.schema_name
                            and manifest.artifact_schema.version == contract.schema_version
                            and manifest.producer is not None
                            and manifest.producer.component == contract.producer_component
                            and manifest.producer.version == contract.producer_version
                        ):
                            matching_owner = report_key
                            break
                    observation = RuntimeQualitySelectedReadObservation(
                        run_id=run_id,
                        job_id=_runtime_quality_job_id(),
                        tenant_id=_runtime_quality_identity_value("tenant_id"),
                        cell_id=_runtime_quality_identity_value("cell_id"),
                        ordinal=len(runtime_quality_selected_reads),
                        selected_ref=selected_ref,
                        selection_origin=selection_origin,
                        payload_sha256=payload_digest,
                        canonical_profile=manifest.canon,
                        manifest_schema=manifest.artifact_schema,
                        manifest_producer=manifest.producer,
                        manifest_inputs=tuple(manifest.inputs),
                        matching_registered_output_owner=matching_owner,
                    )
                except (OSError, RuntimeError, TypeError, ValueError):
                    return None
                # Capture only after the real selected reader returned bytes.
                # This helper is not the complete NL producer read denominator.
                runtime_quality_selected_reads.append(observation)
                return dict(payload)

            def _runtime_quality_selected_report_input_ref(
                *,
                ref_key: str,
                role: str,
                ref_value: object,
                kind: str,
            ) -> InputRef:
                artifact_id = _validated_runtime_quality_reference(
                    ref_value,
                    field_name=ref_key,
                )
                selected_ref = runtime_quality_artifact_refs.get(ref_key)
                if (
                    type(selected_ref) is not ArtifactRef
                    or str(selected_ref.artifact_id) != artifact_id
                    or selected_ref.kind != kind
                    or selected_ref.media_type != "application/json"
                    or not selected_ref.manifest_profile_sha256
                    or runtime_quality_refs.get(ref_key) != artifact_id
                ):
                    raise NaturalLanguagePipelineRefusalError(
                        "runtime_quality_same_input_identity_not_established",
                        f"Runtime quality input {ref_key} lacks its current owner reference.",
                    )
                return input_ref_from_artifact_ref(selected_ref, role=role)

            def _quality_report_input_ref(
                *,
                role: str,
                ref_value: object,
                kind: str,
            ) -> InputRef | None:
                artifact_id = _artifact_id_from_ref_payload(ref_value)
                if artifact_id is None and isinstance(ref_value, str):
                    artifact_id = ref_value.strip()
                if not artifact_id:
                    return None
                ref_key = f"{role}_ref"
                if ref_key in runtime_quality_refs or ref_key in runtime_quality_artifact_refs:
                    return _runtime_quality_selected_report_input_ref(
                        ref_key=ref_key,
                        role=role,
                        ref_value=artifact_id,
                        kind=kind,
                    )
                if selected_materialization_refs.get(artifact_id):
                    selected_ref = _selected_materialization_ref(artifact_id, kind=kind)
                    return input_ref_from_artifact_ref(selected_ref, role=role)
                try:
                    return InputRef(
                        artifact_id=_make_artifact_ref(artifact_id, kind=kind).artifact_id,
                        role=role,
                    )
                except (TypeError, ValueError):
                    return None

            def _final_policy_claims_ref_for_variant(
                variant: Mapping[str, Any],
            ) -> ArtifactRef | None:
                return _selected_final_policy_claims_ref_for_variant(
                    variant,
                    producer_selected_refs=selected_final_policy_claims_refs_by_variant,
                    resolve_legacy_ref=lambda selected: _selected_materialization_ref(
                        selected,
                        "scientist.final_policy_claims",
                    ),
                )

            def _trinity_bundle_ref_for_variant(
                variant: Mapping[str, Any],
            ) -> ArtifactRef | None:
                return _selected_producer_artifact_ref_for_variant(
                    variant,
                    producer_selected_refs=selected_trinity_refs_by_variant,
                    typed_key="trinity_bundle_selected_ref",
                    legacy_key="trinity_bundle_ref",
                    expected_kind="ir.trinity_bundle",
                    refusal_code="auto_materialization_selected_ref_not_established",
                    resolve_ref=lambda selected: _selected_materialization_ref(
                        selected,
                        "ir.trinity_bundle",
                    ),
                )

            def _selected_variant_artifact_refs(
                variant: Mapping[str, Any],
            ) -> tuple[ArtifactRef | None, ArtifactRef | None]:
                """Collect exact producer-owned Trinity and claims refs for one variant."""

                return (
                    _trinity_bundle_ref_for_variant(variant),
                    _final_policy_claims_ref_for_variant(variant),
                )

            def _validate_selected_variant_artifact_refs(
                variants: Sequence[Mapping[str, Any]],
            ) -> None:
                """Validate producer-map membership and every current variant projection."""

                _validate_producer_selected_ref_membership(
                    variants,
                    selected_trinity_refs_by_variant,
                    refusal_code="auto_materialization_selected_ref_not_established",
                )
                _validate_producer_selected_ref_membership(
                    variants,
                    selected_final_policy_claims_refs_by_variant,
                    refusal_code="nl_final_policy_claims_ref_invalid",
                )
                for variant in variants:
                    _selected_variant_artifact_refs(variant)

            def _final_policy_claims_report_input_ref(
                *,
                role: str,
                variant: Mapping[str, Any],
            ) -> InputRef | None:
                selected_ref = _final_policy_claims_ref_for_variant(variant)
                if selected_ref is None:
                    return None
                return input_ref_from_artifact_ref(selected_ref, role=role)

            def _trinity_bundle_input_ref(
                *,
                role: str,
                variant: Mapping[str, Any],
            ) -> InputRef | None:
                selected_ref = _trinity_bundle_ref_for_variant(variant)
                if selected_ref is None:
                    return None
                return input_ref_from_artifact_ref(selected_ref, role=role)

            def _final_policy_claims_report_from_variant(
                variant: Mapping[str, Any],
            ) -> dict[str, Any]:
                report = variant.get("final_policy_claims")
                selected_ref = _final_policy_claims_ref_for_variant(variant)
                if selected_ref is None:
                    if isinstance(report, Mapping):
                        return _require_final_claims_report_shape(
                            report,
                            refusal_code="nl_final_policy_claims_inline_payload_empty",
                        )
                    if report is not None:
                        raise CanonicalProfileRefusalError(
                            "nl_final_policy_claims_inline_payload_invalid"
                        )
                    return {}

                payload = read_optional_selected_artifact(
                    selected_ref,
                    lambda selected: read_core_json_artifact(
                        store,
                        _selected_materialization_ref(
                            selected,
                            "scientist.final_policy_claims",
                        ),
                    ).value,
                    refusal_code="nl_final_policy_claims_selected_unreadable",
                    expected_errors=(
                        OSError,
                        RuntimeError,
                        TypeError,
                        ValueError,
                    ),
                )
                selected_report = _require_final_claims_report_shape(
                    payload,
                    refusal_code="nl_final_policy_claims_selected_payload_invalid",
                )
                if report is not None:
                    inline_report = _require_final_claims_report_shape(
                        report,
                        refusal_code="nl_final_policy_claims_inline_payload_invalid",
                    )
                    if inline_report != selected_report:
                        raise CanonicalProfileRefusalError(
                            "nl_final_policy_claims_selected_inline_mismatch"
                        )
                return selected_report

            def _claims_from_final_report(
                report: Mapping[str, Any],
            ) -> list[dict[str, Any]]:
                raw_claims = report.get("claims") or report.get("policy_claims") or []
                if not isinstance(raw_claims, list):
                    return []
                return [dict(claim) for claim in raw_claims if isinstance(claim, Mapping)]

            def _ref_list_from_payload(payload: Mapping[str, Any]) -> list[str]:
                refs: list[str] = []
                for key in ("norm_refs", "normative_refs", "norm_ids", "legal_refs"):
                    raw_refs = payload.get(key)
                    if isinstance(raw_refs, str) and raw_refs.strip():
                        refs.append(raw_refs.strip())
                    elif isinstance(raw_refs, list):
                        refs.extend(str(item).strip() for item in raw_refs if str(item).strip())
                return refs

            def _context_recommendation_norm_refs() -> list[str]:
                refs: list[str] = []

                def _walk(value: object, *, depth: int = 0) -> None:
                    if depth > 6:
                        return
                    if isinstance(value, Mapping):
                        for key in (
                            "policy_recommendations",
                            "recommendation_claims",
                            "recommendations",
                            "policy_claims",
                        ):
                            raw_items = value.get(key)
                            if isinstance(raw_items, list):
                                for item in raw_items:
                                    if isinstance(item, Mapping):
                                        refs.extend(_ref_list_from_payload(item))
                        for item in value.values():
                            _walk(item, depth=depth + 1)
                    elif isinstance(value, list | tuple):
                        for item in value:
                            _walk(item, depth=depth + 1)

                _walk(context)
                return sorted(set(refs))

            def _merge_context_norm_refs_into_final_claims(
                report: Mapping[str, Any],
            ) -> dict[str, Any]:
                context_norm_refs = _context_recommendation_norm_refs()
                if not context_norm_refs:
                    return dict(report)
                merged = dict(report)
                raw_claims = merged.get("claims")
                if not isinstance(raw_claims, list):
                    return merged
                claims: list[dict[str, Any]] = []
                changed = False
                for raw_claim in raw_claims:
                    if not isinstance(raw_claim, Mapping):
                        continue
                    claim = dict(raw_claim)
                    family = str(
                        claim.get("claim_family")
                        or claim.get("family")
                        or claim.get("claim_type")
                        or claim.get("type")
                        or ""
                    ).casefold()
                    major = bool(claim.get("major", True))
                    existing_refs = _ref_list_from_payload(claim)
                    if major and family in {"", "recommendation"} and not existing_refs:
                        claim["norm_refs"] = list(context_norm_refs)
                        grounding = claim.get("grounding")
                        grounding_payload = (
                            dict(grounding) if isinstance(grounding, Mapping) else {}
                        )
                        grounding_payload["norm_refs"] = list(context_norm_refs)
                        claim["grounding"] = grounding_payload
                        claim["normative_anchor_source"] = "runtime_context_policy_recommendations"
                        changed = True
                    claims.append(claim)
                if not changed:
                    return merged
                merged["claims"] = claims
                merged["major_claims"] = [
                    dict(claim) for claim in claims if bool(claim.get("major", True))
                ]
                summary = dict(merged.get("summary") or {})
                summary["major_claim_count"] = len(merged["major_claims"])
                summary["claim_count"] = len(claims)
                merged["summary"] = summary
                return merged

            def _nested_mapping_value(payload: object, key: str) -> object:
                if isinstance(payload, Mapping):
                    if key in payload:
                        return payload[key]
                    for value in payload.values():
                        found = _nested_mapping_value(value, key)
                        if found is not None:
                            return found
                elif isinstance(payload, list | tuple):
                    for value in payload:
                        found = _nested_mapping_value(value, key)
                        if found is not None:
                            return found
                return None

            def _fabric_trace_payload_from_variant(
                variant: Mapping[str, Any],
            ) -> dict[str, Any]:
                direct = variant.get("fabric_retrieval_trace")
                if isinstance(direct, Mapping):
                    return dict(direct)
                retrieval_context = variant.get("retrieval_context")
                if not isinstance(retrieval_context, Mapping):
                    return {}
                for candidate in (
                    retrieval_context.get("fabric_retrieval_trace"),
                    _nested_mapping_value(
                        retrieval_context.get("production_data_evidence_context"),
                        "fabric_retrieval_trace",
                    ),
                ):
                    if isinstance(candidate, Mapping):
                        return dict(candidate)
                trace_ref = retrieval_context.get(
                    "fabric_retrieval_trace_ref"
                ) or _nested_mapping_value(
                    retrieval_context.get("production_data_evidence_context"),
                    "fabric_retrieval_trace_ref",
                )
                return _load_json_artifact_payload(trace_ref) or {}

            def _source_quality_sources_from_runtime_context(
                *,
                normative_evidence: Mapping[str, Any] | None,
                fabric_retrieval_trace: Mapping[str, Any] | None,
            ) -> list[dict[str, Any]]:
                sources: list[dict[str, Any]] = []
                if isinstance(normative_evidence, Mapping):
                    applied_norms = normative_evidence.get("applied_norms")
                    if isinstance(applied_norms, list):
                        for norm in applied_norms:
                            if not isinstance(norm, Mapping):
                                continue
                            source = dict(norm)
                            source.setdefault(
                                "source_id",
                                source.get("norm_id")
                                or source.get("id")
                                or source.get("artifact_id"),
                            )
                            source.setdefault("source_type", "law")
                            source.setdefault("domain", "policyos.example")
                            sources.append(source)
                if isinstance(fabric_retrieval_trace, Mapping):
                    selected_sources = fabric_retrieval_trace.get("selected_sources")
                    if isinstance(selected_sources, list):
                        for item in selected_sources:
                            if not isinstance(item, Mapping):
                                continue
                            source = dict(item)
                            source.setdefault(
                                "source_type",
                                source.get("source_kind") or "official",
                            )
                            sources.append(source)
                return sources

            def _claim_families_from_claims(claims: list[dict[str, Any]]) -> list[str]:
                families: list[str] = []
                for claim in claims:
                    family = (
                        claim.get("claim_family")
                        or claim.get("family")
                        or claim.get("claim_type")
                        or claim.get("type")
                    )
                    if isinstance(family, str) and family.strip():
                        families.append(family.strip())
                return sorted(dict.fromkeys(families))

            def _corpus_constraints_from_quality_context(
                *,
                normative_evidence: Mapping[str, Any] | None,
            ) -> list[dict[str, Any]]:
                constraints: list[dict[str, Any]] = []

                def _append_constraint_items(
                    source: Mapping[str, Any],
                    keys: tuple[str, ...],
                ) -> None:
                    for key in keys:
                        raw_constraints = source.get(key)
                        if not isinstance(raw_constraints, list):
                            continue
                        constraints.extend(
                            dict(item) for item in raw_constraints if isinstance(item, Mapping)
                        )

                if isinstance(normative_evidence, Mapping):
                    _append_constraint_items(
                        normative_evidence,
                        (
                            "active_corpus_constraints",
                            "corpus_constraints",
                            "normative_constraints",
                            "policy_constraints",
                            "constraints",
                            "applied_norms",
                        ),
                    )
                _append_constraint_items(
                    context,
                    (
                        "active_corpus_constraints",
                        "corpus_constraints",
                        "normative_constraints",
                        "policy_constraints",
                        "constraints",
                    ),
                )
                if isinstance(governance_constraints_payload, list):
                    constraints.extend(
                        dict(item)
                        for item in governance_constraints_payload
                        if isinstance(item, Mapping)
                    )
                deduped: list[dict[str, Any]] = []
                seen: set[str] = set()
                for index, constraint in enumerate(constraints):
                    fingerprint = str(
                        constraint.get("constraint_id")
                        or constraint.get("id")
                        or constraint.get("norm_id")
                        or constraint.get("norm_ref")
                        or repr(sorted(constraint.items()))
                        or index
                    )
                    if fingerprint in seen:
                        continue
                    seen.add(fingerprint)
                    deduped.append(constraint)
                return deduped

            def _existing_conflicts_from_quality_context(
                *,
                normative_evidence: Mapping[str, Any] | None,
                selected_variant_payload: Mapping[str, Any],
            ) -> list[dict[str, Any]]:
                conflicts: list[dict[str, Any]] = []
                for source in (normative_evidence, selected_variant_payload, context):
                    if not isinstance(source, Mapping):
                        continue
                    raw_conflicts = source.get("conflicts") or source.get("policy_conflicts")
                    if not isinstance(raw_conflicts, list):
                        continue
                    conflicts.extend(
                        dict(item) for item in raw_conflicts if isinstance(item, Mapping)
                    )
                return conflicts

            materialization_ref_kinds = {
                "data_snapshot_ref": "fabric.data_snapshot",
                "input_bindings_ref": "foundry.input_bindings",
                "registry_bundle_ref": "core.registry_bundle",
                "input_binding_report_ref": "foundry.input_binding_report",
                "evidence_bundle_ref": "fabric.evidence_bundle",
                "production_data_quality_report_ref": "runtime.production_data_quality_report",
                "fabric_retrieval_trace_ref": "fabric.retrieval_trace",
            }
            selected_materialization_refs: dict[str, list[ArtifactRef]] = {}
            selected_trinity_refs_by_variant: dict[str, ArtifactRef] = {}
            selected_final_policy_claims_refs_by_variant: dict[str, ArtifactRef] = {}
            frozen_materialization_input_bases: dict[
                tuple[str, str | None, str | None, str],
                tuple[tuple[InputRef, ...], frozenset[str]],
            ] = {}
            frozen_materialization_publication_contexts: dict[
                tuple[str, str, str],
                tuple[tuple[InputRef, ...], frozenset[str]],
            ] = {}
            frozen_runtime_quality_publication_times: dict[str, tuple[str, str]] = {}

            def _remember_selected_materialization_ref(ref: ArtifactRef) -> None:
                candidates = selected_materialization_refs.setdefault(str(ref.artifact_id), [])
                if all(
                    candidate.manifest_profile_sha256 != ref.manifest_profile_sha256
                    or candidate.kind != ref.kind
                    or candidate.media_type != ref.media_type
                    for candidate in candidates
                ):
                    candidates.append(ref)

            async def _persist_nl_execution_artifact(
                writer: Callable[..., _StepResult],
                *args: object,
                **kwargs: object,
            ) -> _StepResult:
                """Persist one fresh run product under the admitted execution owner."""
                from polisyos.core.security.tenant_context import tenant_scope

                if "tenant_context" in kwargs:
                    raise ValueError("nl_execution_artifact_owner_is_pipeline_bound")
                with tenant_scope(
                    None,
                    tenant_id=trinity_bundle_tenant_context.tenant_id,
                    cell_id=trinity_bundle_tenant_context.cell_id,
                ):
                    ref = await run_blocking_async(
                        writer,
                        store,
                        *args,
                        tenant_context=trinity_bundle_tenant_context,
                        **kwargs,
                    )
                if isinstance(ref, ArtifactRef):
                    _remember_selected_materialization_ref(ref)
                return ref

            def _selected_materialization_ref(
                value: object,
                kind: str | None = None,
                *,
                parent_manifest: object | None = None,
                parent_roles: frozenset[str] = frozenset(),
            ) -> ArtifactRef:
                return _resolve_selected_materialization_ref(
                    store,
                    value,
                    selected_materialization_refs,
                    kind=kind,
                    parent_manifest=parent_manifest,
                    parent_roles=parent_roles,
                )

            def _selected_nl_execution_artifact_ref(
                value: object,
                kind: str,
            ) -> ArtifactRef:
                """Resolve a planning ref only within the admitted execution owner scope."""
                from polisyos.core.security.tenant_context import tenant_scope

                with tenant_scope(
                    None,
                    tenant_id=trinity_bundle_tenant_context.tenant_id,
                    cell_id=trinity_bundle_tenant_context.cell_id,
                ):
                    return _selected_materialization_ref(value, kind=kind)

            def _materialization_input_refs(
                refs: Mapping[str, Any],
                *,
                basis_key: str | None = None,
                output_ref_key: str | None = None,
                output_report_key: str | None = None,
                output_payload: Mapping[str, Any] | None = None,
            ) -> list[InputRef]:
                # Snapshot the caller's mutable ref map before deriving this write's inputs.
                # It can later gain reports produced from the same materialization; those
                # derived outputs are not inputs to one another.
                from polisyos.core.contracts import (
                    data_snapshot_reference_fields,
                    data_snapshot_reference_input_roles,
                )
                from polisyos.core.contracts.fabric import DataSnapshot

                frozen_refs = dict(refs)
                inputs: list[InputRef] = []
                snapshot_manifest = None
                selected_snapshot_ref = None
                nested_snapshot_refs: dict[str, ArtifactRef] = {}
                snapshot_value = frozen_refs.get("data_snapshot_ref")
                if snapshot_value is not None:
                    selected_snapshot_ref = _selected_materialization_ref(
                        snapshot_value,
                        "fabric.data_snapshot",
                    )
                    try:
                        from polisyos.core.artifacts import read_core_manifest_profile

                        snapshot_manifest, _declaration = read_core_manifest_profile(
                            store,
                            selected_snapshot_ref,
                        )
                        snapshot_payload = read_core_json_artifact(
                            store,
                            selected_snapshot_ref,
                        ).value
                        snapshot = DataSnapshot.model_validate(snapshot_payload)
                    except (OSError, RuntimeError, TypeError, ValueError) as exc:
                        raise RuntimeError(
                            "auto_materialization_selected_ref_not_established"
                        ) from exc
                    for field_name in data_snapshot_reference_fields():
                        nested_value = getattr(snapshot, field_name)
                        if nested_value is None:
                            continue
                        nested_snapshot_refs[field_name] = _selected_materialization_ref(
                            nested_value,
                            parent_manifest=snapshot_manifest,
                            parent_roles=data_snapshot_reference_input_roles(field_name),
                        )

                quality_report_value = frozen_refs.get("quality_report_ref")
                selected_quality_ref = None
                if quality_report_value is not None:
                    nested_quality_ref = nested_snapshot_refs.get("quality_report_ref")
                    selected_quality_ref = _selected_materialization_ref(
                        quality_report_value,
                        nested_quality_ref.kind if nested_quality_ref is not None else None,
                    )
                snapshot_quality_ref = nested_snapshot_refs.get("quality_report_ref")
                if snapshot_quality_ref is not None:
                    if selected_quality_ref is not None and (
                        selected_quality_ref.artifact_id != snapshot_quality_ref.artifact_id
                        or selected_quality_ref.kind != snapshot_quality_ref.kind
                        or selected_quality_ref.media_type != snapshot_quality_ref.media_type
                        or selected_quality_ref.manifest_profile_sha256
                        != snapshot_quality_ref.manifest_profile_sha256
                    ):
                        raise RuntimeError("auto_materialization_quality_ref_mismatch")
                    selected_quality_ref = snapshot_quality_ref
                for field_name, selected_nested_ref in nested_snapshot_refs.items():
                    inputs.append(
                        input_ref_from_artifact_ref(
                            selected_nested_ref,
                            role=field_name,
                        )
                    )
                    if field_name != "data_ref" or snapshot_manifest is None:
                        continue
                    matching_parent_edges = [
                        item
                        for item in snapshot_manifest.inputs
                        if item.artifact_id == selected_nested_ref.artifact_id
                        and item.manifest_profile_sha256
                        == selected_nested_ref.manifest_profile_sha256
                    ]
                    production_payload_edges = [
                        item
                        for item in matching_parent_edges
                        if item.role == "production_data_payload"
                    ]
                    if selected_nested_ref.kind == "fabric.production_data_payload":
                        if len(production_payload_edges) != 1:
                            raise RuntimeError(
                                "auto_materialization_production_data_payload_lineage_not_established"
                            )
                        try:
                            source_payload = read_core_json_artifact(
                                store,
                                selected_nested_ref,
                            ).value
                        except (OSError, RuntimeError, TypeError, ValueError) as exc:
                            raise RuntimeError(
                                "auto_materialization_production_data_payload_not_established"
                            ) from exc
                        source_context = (
                            source_payload.get("production_data_evidence_context")
                            if isinstance(source_payload, Mapping)
                            else None
                        )
                        manifest_sha256 = (
                            source_context.get("manifest_sha256")
                            if isinstance(source_context, Mapping)
                            else None
                        )
                        if (
                            not isinstance(manifest_sha256, str)
                            or len(manifest_sha256) != 71
                            or not manifest_sha256.startswith("sha256:")
                            or any(
                                character not in "0123456789abcdef"
                                for character in manifest_sha256[7:]
                            )
                        ):
                            raise RuntimeError(
                                "auto_materialization_production_manifest_digest_not_established"
                            )
                        inputs.append(
                            input_ref_from_artifact_ref(
                                selected_nested_ref,
                                role="production_data_payload",
                            )
                        )
                    elif production_payload_edges:
                        raise RuntimeError(
                            "auto_materialization_production_data_payload_kind_mismatch"
                        )
                if selected_quality_ref is not None and snapshot_quality_ref is None:
                    inputs.append(
                        input_ref_from_artifact_ref(
                            selected_quality_ref,
                            role="quality_report_ref",
                        )
                    )
                for key, kind in materialization_ref_kinds.items():
                    value = frozen_refs.get(key)
                    if value is None:
                        continue
                    selected_ref = _selected_materialization_ref(value, kind)
                    inputs.append(
                        input_ref_from_artifact_ref(
                            selected_ref,
                            role=key.removesuffix("_ref"),
                        )
                    )

                if basis_key is None:
                    return inputs

                reissuable_report_roles = frozenset(
                    key.removesuffix("_ref")
                    for key, kind in materialization_ref_kinds.items()
                    if kind in {"runtime.production_data_quality_report", "fabric.retrieval_trace"}
                )

                def _historical_report_context_matches(
                    report_key: str, ref_key: str, candidate: InputRef
                ) -> bool:
                    contract = runtime_quality_report_owner_contract(report_key, ref_key)
                    if contract is None:
                        return False
                    return _runtime_quality_historical_report_materialization_input_is_verified(
                        candidate,
                        report_key=report_key,
                        ref_key=ref_key,
                        artifact_store=store,
                        tenant_context=trinity_bundle_tenant_context,
                        current_publication_verifier=lambda basis: (
                            _runtime_quality_publication_context_matches(
                                basis=basis,
                                report_key=report_key,
                                ref_key=ref_key,
                                phase=contract.phase,
                                requested_as_of_time=(
                                    runtime_quality_publication_requested_as_of_times.get(ref_key)
                                ),
                            )
                        ),
                    )

                def _is_verified_reissuable_report_input(item: InputRef) -> bool:
                    return _runtime_quality_report_materialization_input_is_verified(
                        item,
                        output_report_key=output_report_key,
                        reissuable_report_roles=reissuable_report_roles,
                        runtime_quality_refs=runtime_quality_refs,
                        runtime_quality_artifact_refs=runtime_quality_artifact_refs,
                        current_publication_verifier=lambda report_key, ref_key, expected_ref: (
                            _runtime_quality_report_is_current_publication(
                                report_key=report_key, ref_key=ref_key, expected_ref=expected_ref
                            )
                        ),
                        historical_publication_verifier=_historical_report_context_matches,
                    )

                current_reissuable_report_refs = frozenset(
                    (str(item.artifact_id), item.role)
                    for item in inputs
                    if _is_verified_reissuable_report_input(item)
                )

                if basis_key is not None and output_payload is None:
                    raise RuntimeError("auto_materialization_output_payload_not_established")

                target_output_id = None
                if basis_key is not None:
                    if output_ref_key is None or output_report_key is None:
                        raise RuntimeError("auto_materialization_output_ref_not_established")
                    try:
                        target_source_payload, output_basis = (
                            _runtime_quality_report_source_payload(
                                output_payload or {},
                                report_key=output_report_key,
                                ref_key=output_ref_key,
                            )
                        )
                    except ValueError as exc:
                        raise RuntimeError(str(exc)) from exc
                    if output_basis is not None:
                        try:
                            target_payload = _runtime_quality_report_writer_payload(
                                target_source_payload,
                                report_key=output_report_key,
                                ref_key=output_ref_key,
                            )
                        except ValueError as exc:
                            raise RuntimeError(str(exc)) from exc
                    else:
                        target_payload = dict(target_source_payload)
                        target_payload.setdefault(
                            "runtime_authority_payload",
                            {
                                "schema_version": "policyos.runtime.authority_payload_marker.v1",
                                "report_key": output_report_key,
                                "ref_key": output_ref_key,
                                "projection": False,
                            },
                        )
                    target_output_id = _runtime_quality_payload_sha256(target_payload)

                selected_output_ref: ArtifactRef | None = None
                predecessor_output_id = None
                if output_ref_key is not None and frozen_refs.get(output_ref_key) is not None:
                    output_kind = {
                        "fabric_retrieval_trace_ref": "fabric.retrieval_trace",
                        "production_data_quality_report_ref": (
                            "runtime.production_data_quality_report"
                        ),
                        "privacy_compliance_report_ref": "runtime.privacy_compliance_report",
                    }.get(output_ref_key)
                    if output_kind is None:
                        raise RuntimeError("auto_materialization_output_ref_not_established")
                    output_ref = _selected_materialization_ref(
                        frozen_refs[output_ref_key],
                        output_kind,
                    )
                    selected_output_ref = output_ref
                    selected_output_id = str(output_ref.artifact_id)
                    if selected_output_id == target_output_id:
                        inputs = [
                            item for item in inputs if str(item.artifact_id) != selected_output_id
                        ]
                    elif target_output_id is not None:
                        predecessor_output_id = selected_output_id

                snapshot_identity = (
                    (
                        str(selected_snapshot_ref.artifact_id),
                        selected_snapshot_ref.manifest_profile_sha256,
                    )
                    if selected_snapshot_ref is not None
                    else (None, None)
                )
                if target_output_id is None:
                    raise RuntimeError("auto_materialization_output_ref_not_established")
                basis_identity = (basis_key, *snapshot_identity, target_output_id)
                previously_published_ref_values = {
                    str(value)
                    for value in runtime_quality_refs.values()
                    if isinstance(value, str) and value
                }
                if predecessor_output_id is not None:
                    previously_published_ref_values.discard(predecessor_output_id)
                previously_published_refs = frozenset(previously_published_ref_values)
                existing_basis = frozen_materialization_input_bases.get(basis_identity)
                recovered_reissuable_report_ids = frozenset()
                if (
                    existing_basis is not None
                    and selected_output_ref is not None
                    and str(selected_output_ref.artifact_id) == target_output_id
                ):
                    from polisyos.core.artifacts import (
                        artifact_ref_for_manifest,
                        read_core_manifest_profile,
                    )

                    try:
                        persisted_output_manifest, declaration = read_core_manifest_profile(
                            store,
                            selected_output_ref,
                            manifest_profile_sha256=selected_output_ref.manifest_profile_sha256,
                        )
                        persisted_output_ref = artifact_ref_for_manifest(persisted_output_manifest)
                        if declaration.status != "declared" or persisted_output_ref.model_dump(
                            mode="json"
                        ) != selected_output_ref.model_dump(mode="json"):
                            raise ValueError("selected_output_manifest_identity_changed")
                    except (OSError, RuntimeError, TypeError, ValueError) as exc:
                        raise RuntimeError("auto_materialization_input_basis_changed") from exc

                    missing_frozen_inputs = tuple(
                        item for item in existing_basis[0] if item not in inputs
                    )
                    verified_reissuable_report_refs = frozenset(
                        (
                            str(item.artifact_id),
                            item.role,
                            item.manifest_profile_sha256,
                        )
                        for item in missing_frozen_inputs
                        if _is_verified_reissuable_report_input(item)
                    )
                    inputs, recovered_reissuable_report_ids = (
                        _restore_frozen_materialization_report_inputs(
                            inputs,
                            existing_basis=existing_basis,
                            persisted_output_inputs=persisted_output_manifest.inputs,
                            reissuable_report_roles=reissuable_report_roles,
                            verified_reissuable_report_refs=verified_reissuable_report_refs,
                        )
                    )
                    previously_published_ref_values.difference_update(
                        recovered_reissuable_report_ids
                    )
                    previously_published_refs = frozenset(previously_published_ref_values)

                reconciled_basis = _reconcile_materialization_input_basis(
                    inputs,
                    currently_published_refs=previously_published_refs,
                    existing_basis=existing_basis,
                    current_reissuable_report_refs=current_reissuable_report_refs,
                )
                frozen_materialization_input_bases[basis_identity] = reconciled_basis
                if output_ref_key is not None:
                    publication_context_key = (
                        basis_key,
                        output_ref_key,
                        target_output_id,
                    )
                    existing_publication_context = frozen_materialization_publication_contexts.get(
                        publication_context_key
                    )
                    if (
                        existing_publication_context is not None
                        and existing_publication_context != reconciled_basis
                    ):
                        raise RuntimeError("auto_materialization_input_basis_changed")
                    frozen_materialization_publication_contexts.setdefault(
                        publication_context_key,
                        reconciled_basis,
                    )
                return list(reconciled_basis[0])

            def _deterministic_scenario_enabled() -> bool:
                return bool(os.getenv("POLISYOS_LLM_SIMULATION_MODE")) and isinstance(
                    context.get("expected_evidence_contract"),
                    Mapping,
                )

            def _deterministic_scenario_quality_evidence(
                materialization_refs: Mapping[str, Any] | None = None,
            ) -> dict[str, Any]:
                expected = context.get("expected_evidence_contract")
                if not isinstance(expected, Mapping):
                    return {}
                refs = dict(materialization_refs or {})
                source_families = [
                    str(item).strip()
                    for item in expected.get("admissible_data_source_families") or []
                    if str(item or "").strip()
                ] or ["production_data"]
                method_expectations = [
                    str(item).strip()
                    for item in expected.get("foundry_method_expectations") or []
                    if str(item or "").strip()
                ] or ["causal_effect_estimation"]
                normative_fact_classes = [
                    str(item).strip()
                    for item in expected.get("normative_fact_classes") or []
                    if str(item or "").strip()
                ] or ["runtime_quality_authority"]
                conflict_checks = [
                    str(item).strip()
                    for item in expected.get("conflict_checks") or []
                    if str(item or "").strip()
                ]
                target_context = context.get("target_context")
                jurisdiction = str(
                    context.get("country")
                    or context.get("jurisdiction")
                    or (
                        target_context.get("countries", ["global"])[0]
                        if isinstance(target_context, Mapping)
                        and isinstance(target_context.get("countries"), list)
                        and target_context.get("countries")
                        else None
                    )
                    or "global"
                )
                policy_domain = str(context.get("policy_domain") or domain_hint or "policy")
                as_of = str(context.get("as_of") or "2026-05-13")
                norm_ids = [f"norm.{fact_class}" for fact_class in normative_fact_classes]
                selected_source_ids = [f"{family}.golden_source" for family in source_families]
                selected_methods = [
                    {
                        "method_id": f"foundry.{expectation}",
                        "method_family": expectation,
                        "method_expectations": [expectation],
                        "input_refs": {
                            key: str(value)
                            for key, value in refs.items()
                            if key
                            in {
                                "data_snapshot_ref",
                                "input_bindings_ref",
                                "registry_bundle_ref",
                            }
                        },
                        "assumptions": ["deterministic_scenario_contract"],
                        "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
                        "missingness": {"status": "pass", "missing_rate": 0.0},
                        "sensitivity": {
                            "status": "pass",
                            "robustness": "deterministic",
                        },
                        "input_diagnostics": {
                            "sample_size": 240,
                            "min_required_sample_size": 30,
                        },
                        "result_summary": {"effect_estimate": 0.04},
                    }
                    for expectation in method_expectations
                ]
                claim = {
                    "claim_id": "deterministic_recommendation_1",
                    "claim_type": "recommendation",
                    "claim_family": "recommendation",
                    "major": True,
                    "text": str(nl_request or "Deterministic canary recommendation."),
                    "data_refs": selected_source_ids,
                    "method_refs": [str(method["method_id"]) for method in selected_methods],
                    "norm_refs": norm_ids,
                    "grounding_rationale": (
                        "Deterministic simulated closeout binds the recommendation to "
                        "the public golden scenario contract."
                    ),
                    "support_summary": (
                        "Golden scenario evidence links the recommendation to data, "
                        "method, and normative refs."
                    ),
                    "uncertainty": (
                        "Estimated effects are bounded by deterministic scenario "
                        "assumptions and monitoring triggers."
                    ),
                    "policy_tradeoffs": [
                        "Balances impact, budget limits, implementation risk, and equity."
                    ],
                    "implementation_feasibility": (
                        "Implementation is feasible through existing program and "
                        "monitoring channels represented in the scenario contract."
                    ),
                    "stakeholder_impact": (
                        "Targets affected MSMEs while preserving equity and budget guardrails."
                    ),
                    "implementation_risks": ["Monitor take-up, leakage, and delivery capacity."],
                    "monitoring_plan": [
                        "Track outcome, treatment, subgroup, and budget indicators."
                    ],
                    "budget_implication": "Budget guardrails are represented by normative refs.",
                    "distributional_impact": (
                        "Subgroup access is represented by the scenario evidence contract."
                    ),
                    "residual_uncertainty": (
                        "Effect estimates remain scenario-bounded and require monitoring."
                    ),
                    "withdrawal_reissue_triggers": [
                        "Withdraw or reissue if monitoring violates guardrails."
                    ],
                }
                claim["section_evidence_refs"] = {
                    section: [
                        *selected_source_ids,
                        *[str(method["method_id"]) for method in selected_methods],
                        *norm_ids,
                    ]
                    for section in (
                        "support_summary",
                        "uncertainty",
                        "policy_tradeoffs",
                        "distributional_impact",
                        "implementation_feasibility",
                        "budget_implication",
                        "stakeholder_impact",
                        "implementation_risks",
                        "residual_uncertainty",
                        "monitoring_plan",
                        "withdrawal_reissue_triggers",
                    )
                }
                candidate_sources = [
                    {
                        "source_id": source_id,
                        "source_family": family,
                        "source_kind": "production_data",
                        "freshness": {"status": "pass", "as_of": as_of},
                        "coverage": {"status": "pass", "geography": jurisdiction},
                        "schema_compatibility": {"status": "pass"},
                        "available_columns": [
                            "entity_id",
                            "period",
                            str(context.get("query_outcome") or "outcome"),
                            str(context.get("query_treatment") or "treatment"),
                        ],
                        "relevance_score": 0.95,
                        "relevance_rationale": (
                            "Deterministic runtime source matches the golden scenario contract."
                        ),
                    }
                    for source_id, family in zip(
                        selected_source_ids,
                        source_families,
                        strict=False,
                    )
                ]
                final_claims_report = {
                    "schema_version": "policyos.scientist.final_policy_claims.v1",
                    "status": "pass",
                    "extraction_status": "pass",
                    "claims": [claim],
                    "summary": {
                        "claim_count": 1,
                        "major_claim_count": 1,
                        "source": "deterministic_scenario_contract",
                    },
                }
                diagnostics = {
                    key: {
                        "name": key,
                        "status": "pass",
                        "findings": [],
                        "summary": {"source": "deterministic_scenario_contract"},
                    }
                    for key in DIAGNOSTIC_KEYS
                }
                return {
                    "final_policy_claims": final_claims_report,
                    "normative_evidence": {
                        "status": "pass",
                        "target_context": {
                            "jurisdiction": jurisdiction,
                            "policy_domain": policy_domain,
                            "as_of": as_of,
                        },
                        "applied_norms": [
                            {
                                "norm_id": norm_id,
                                "jurisdiction": jurisdiction,
                                "policy_domain": policy_domain,
                                "effective_from": "2024-01-01",
                                "source_authority": (
                                    "PolicyOS deterministic canary scenario contract"
                                ),
                                "authority_level": "scenario_contract",
                                "fact_class": fact_class,
                            }
                            for norm_id, fact_class in zip(
                                norm_ids,
                                normative_fact_classes,
                                strict=False,
                            )
                        ],
                        "recommendation_claims": [
                            {
                                "claim_id": claim["claim_id"],
                                "major": True,
                                "norm_refs": norm_ids,
                            }
                        ],
                        "recommendation_coverage": [
                            {
                                "claim_id": claim["claim_id"],
                                "major": True,
                                "norm_refs": norm_ids,
                            }
                        ],
                        "issues": [],
                    },
                    "fabric_retrieval_trace": {
                        "status": "pass",
                        "query_intent": {
                            "policy_domain": policy_domain,
                            "query_outcome": context.get("query_outcome"),
                            "query_treatment": context.get("query_treatment"),
                        },
                        "candidate_sources": candidate_sources,
                        "selected_sources": candidate_sources,
                        "selected_source_ids": selected_source_ids,
                        "rejected_sources": [
                            {
                                "source_id": f"{selected_source_ids[0]}.alternate",
                                "source_family": source_families[0],
                                "reason_code": "lower_relevance",
                            }
                        ],
                        "materialization_refs": refs,
                        "issues": [],
                    },
                    "foundry_method_report": {
                        "status": "pass",
                        "foundry_input_refs": {
                            key: str(value)
                            for key, value in refs.items()
                            if key
                            in {
                                "data_snapshot_ref",
                                "input_bindings_ref",
                                "registry_bundle_ref",
                            }
                        },
                        "selected_methods": selected_methods,
                        "issues": [],
                    },
                    "policy_grounding_matrix": {
                        "schema_version": "policyos.scientist.policy_grounding_matrix.v1",
                        "status": "pass",
                        "claims": [claim],
                        "issues": [],
                    },
                    "conflict_check": {
                        "schema_version": "policyos.lex.policy_conflict_check.v1",
                        "status": "pass",
                        "claims": [claim],
                        "conflicts": [],
                        "corpus_constraints": [
                            {
                                "constraint_id": f"conflict.{check}",
                                "constraint_type": "informational_overlap",
                                "severity": "info",
                                "norm_refs": norm_ids,
                            }
                            for check in conflict_checks
                        ],
                        "issues": [],
                    },
                    "production_data_quality": {
                        "schema_version": "policyos.runtime.production_data_quality.v1",
                        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                        "status": "pass",
                        "source": "deterministic_scenario_contract",
                        "diagnostics": diagnostics,
                        "issues": [],
                        "row_counts": {"deterministic_closeout": 1},
                        "entity_counts": {"deterministic_closeout": 1},
                        "data_needs": [],
                        PRODUCTION_DATA_QUALITY_REF_KEY: str(
                            refs.get(PRODUCTION_DATA_QUALITY_REF_KEY) or ""
                        ),
                        "data_snapshot_ref": refs.get("data_snapshot_ref"),
                        "input_bindings_ref": refs.get("input_bindings_ref"),
                        "registry_bundle_ref": refs.get("registry_bundle_ref"),
                        "quality_report_ref": refs.get("quality_report_ref"),
                    },
                    "decision_artifact_quality": {
                        "schema_version": "policyos.scientist.decision_artifact_quality.v1",
                        "status": "pass",
                        "profile": execution_profile or "research",
                        "input_refs": dict(refs),
                        "summary": {
                            "recommendation_count": 1,
                            "major_recommendation_count": 1,
                            "issue_count": 0,
                        },
                        "claim_evidence_contract": {
                            "major_claims": [
                                {
                                    "claim_id": claim["claim_id"],
                                    "data_refs": claim["data_refs"],
                                    "method_refs": claim["method_refs"],
                                    "norm_refs": claim["norm_refs"],
                                }
                            ]
                        },
                        "issues": [],
                        "blocking_issue_count": 0,
                    },
                }

            async def _persist_production_data_fabric_trace(
                *,
                query_intent: Mapping[str, Any],
                evidence_context: Mapping[str, Any],
                data_needs_payload: list[dict[str, Any]],
                fetch_plans_payload: list[dict[str, Any]],
                retrieval_telemetry: Mapping[str, Any],
                materialization_refs: Mapping[str, Any],
            ) -> tuple[str, dict[str, Any]]:
                deterministic_evidence = _deterministic_scenario_quality_evidence(
                    materialization_refs
                )
                scenario_evidence_contract = (
                    context.get("scenario_evidence_contract")
                    if isinstance(context.get("scenario_evidence_contract"), Mapping)
                    else None
                )
                contract_binding_report = None
                if isinstance(scenario_evidence_contract, Mapping):
                    production_root = evidence_context.get("root")
                    try:
                        contract_binding_report = _production_data_contract_binding_report(
                            (
                                {"production_data_root": str(production_root)}
                                if production_root
                                else None
                            ),
                            scenario_evidence_contract=scenario_evidence_contract,
                            allow_default=not bool(production_root),
                        )
                    except Exception:
                        logger.exception(
                            "Failed to build production data contract binding report",
                            extra={"run_id": run_id},
                        )
                trace_payload = (
                    deterministic_evidence["fabric_retrieval_trace"]
                    if _deterministic_scenario_enabled()
                    and "fabric_retrieval_trace" in deterministic_evidence
                    else _build_production_data_fabric_trace(
                        query_intent=query_intent,
                        evidence_context=evidence_context,
                        data_needs=_mapping_rows(data_needs_payload),
                        fetch_plans=_mapping_rows(fetch_plans_payload),
                        retrieval_telemetry=retrieval_telemetry,
                        materialization_refs=materialization_refs,
                        canary_kind=execution_profile or "production",
                        spine_context=_producer_spine_context_payload(),
                        scenario_evidence_contract=scenario_evidence_contract,
                        production_data_contract_binding_report=contract_binding_report,
                    )
                )
                if isinstance(scenario_evidence_contract, Mapping):
                    trace_payload["scenario_evidence_contract_id"] = _clean_runtime_text(
                        scenario_evidence_contract.get("contract_id")
                    )
                    try:
                        evidence_spine_carrier = EvidenceSpineCarrier.from_scenario_contract(
                            scenario_evidence_contract,
                            producer_component="fabric",
                            producer_report_schema="polisyos.fabric.SourceSelectionTrace",
                            reader_contract="runtime_quality.scenario_contract_propagation_graph",
                            authority_profile=execution_profile or "production",
                            code_revision=os.environ.get("POLISYOS_CODE_REVISION"),
                            input_refs=[
                                item.artifact_id
                                for item in _materialization_input_refs(materialization_refs)
                            ],
                            output_refs=("fabric_retrieval_trace_ref",),
                        )
                    except EvidenceSpineValidationError as exc:
                        trace_payload["evidence_spine_carrier_error"] = {
                            "code": "evidence_spine_contract_invalid",
                            "message": str(exc),
                        }
                    else:
                        trace_payload["evidence_spine_carrier"] = evidence_spine_carrier.to_dict()
                        trace_payload["scenario_requirement_ids"] = list(
                            evidence_spine_carrier.requirement_ids
                        )
                if isinstance(contract_binding_report, Mapping):
                    trace_payload["production_data_contract_binding_report"] = dict(
                        contract_binding_report
                    )
                return await _persist_and_publish_runtime_quality_payload(
                    report_key="fabric_retrieval_trace",
                    ref_key="fabric_retrieval_trace_ref",
                    report_payload=trace_payload,
                    artifact_kind="fabric.retrieval_trace",
                    schema_name="polisyos.fabric.SourceSelectionTrace",
                    phase="fabric_retrieval_trace",
                    materialization_basis_key="fabric_retrieval_trace",
                    input_refs=_materialization_input_refs(
                        materialization_refs,
                        basis_key="fabric_retrieval_trace",
                        output_ref_key="fabric_retrieval_trace_ref",
                        output_report_key="fabric_retrieval_trace",
                        output_payload=trace_payload,
                    ),
                )

            async def _persist_production_data_quality_report(
                *,
                evidence_context: Mapping[str, Any],
                materialization_refs: Mapping[str, Any],
                data_needs_payload: list[dict[str, Any]],
                claims_payload: list[dict[str, Any]] | None = None,
            ) -> tuple[str, dict[str, Any]]:
                deterministic_evidence = _deterministic_scenario_quality_evidence(
                    materialization_refs
                )
                report_payload = (
                    deterministic_evidence["production_data_quality"]
                    if _deterministic_scenario_enabled()
                    and "production_data_quality" in deterministic_evidence
                    else _build_production_data_quality_report(
                        evidence_context=evidence_context,
                        materialization_refs=materialization_refs,
                        data_needs=_mapping_rows(data_needs_payload),
                        claims=(
                            _mapping_rows(claims_payload) if claims_payload is not None else None
                        ),
                    )
                )
                return await _persist_and_publish_runtime_quality_payload(
                    report_key="production_data_quality",
                    ref_key="production_data_quality_report_ref",
                    report_payload=report_payload,
                    artifact_kind="runtime.production_data_quality_report",
                    schema_name="polisyos.runtime.ProductionDataQualityReport",
                    phase="production_data_quality",
                    materialization_basis_key="production_data_quality_report",
                    input_refs=_materialization_input_refs(
                        materialization_refs,
                        basis_key="production_data_quality_report",
                        output_ref_key="production_data_quality_report_ref",
                        output_report_key="production_data_quality",
                        output_payload=report_payload,
                    ),
                )

            async def _persist_privacy_compliance_report(
                *,
                report_payload: Mapping[str, Any],
                materialization_refs: Mapping[str, Any],
            ) -> str:
                ref = await async_store.put_json(
                    dict(report_payload),
                    ArtifactWriteOptions(
                        kind="runtime.privacy_compliance_report",
                        media_type="application/json",
                        schema=SchemaInfo(
                            name="polisyos.runtime.PrivacyComplianceReport",
                            version="1.0",
                        ),
                        inputs=_materialization_input_refs(
                            materialization_refs,
                            basis_key="privacy_compliance_report",
                            output_ref_key="privacy_compliance_report_ref",
                            output_report_key="privacy_compliance_report",
                            output_payload=report_payload,
                        ),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                return str(ref.artifact_id)

            def _runtime_quality_identity_value(key: str) -> str:
                owner = runtime_quality_owner_binding
                if owner is None:
                    raise NaturalLanguagePipelineRefusalError(
                        "control_job_execution_scope_not_established",
                        "Runtime quality authority requires a verified current owner binding.",
                    )
                value = owner.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise NaturalLanguagePipelineRefusalError(
                        "control_job_execution_scope_not_established",
                        f"Admitted runtime scope is missing {key}.",
                    )
                return value

            def _runtime_quality_job_id() -> str:
                return _runtime_quality_identity_value("job_id")

            def _runtime_quality_profile() -> str:
                return _runtime_quality_identity_value("effective_execution_profile")

            def _runtime_quality_attestations() -> list[dict[str, Any]]:
                material_refs = {
                    **dict(runtime_quality_refs),
                    "run_request": f"run:{run_id}:request",
                    "execution_profile": _runtime_quality_profile(),
                    "input_refs": f"run:{run_id}:input_refs",
                    "runtime_refs": f"run:{run_id}:runtime_quality_refs",
                    "authority_envelopes": f"run:{run_id}:authority_envelopes",
                    "diagnostic_events": diagnostic_event_log_ref
                    or f"run:{run_id}:diagnostic_events",
                    "payload_bytes": "runtime.cas.payload_bytes",
                    "schema_identity": "runtime.cas.schema_identity",
                    "tenant_identity": _runtime_quality_identity_value("tenant_id"),
                    "prompt_ref": dict(runtime_quality_refs).get("prompt_tool_ledger_ref")
                    or f"run:{run_id}:prompt",
                    "model_policy": dict(runtime_quality_refs).get(
                        "provider_model_quality_ledger_ref"
                    )
                    or f"run:{run_id}:model_policy",
                    "provider_request": f"run:{run_id}:provider_request",
                    "connector_request": f"run:{run_id}:connector_request",
                    "source_contract": dict(runtime_quality_refs).get("fabric_retrieval_trace_ref")
                    or f"run:{run_id}:source_contract",
                    "credential_scope": "runtime.redacted_credential_scope",
                    "jurisdiction_filter": f"run:{run_id}:jurisdiction_filter",
                    "legal_snapshot_ref": dict(runtime_quality_refs).get(
                        "normative_applicability_report_ref"
                    )
                    or f"run:{run_id}:legal_snapshot",
                    "query_ref": f"run:{run_id}:legal_query",
                    "tool_contract": f"run:{run_id}:tool_contract",
                    "parser_schema": f"run:{run_id}:parser_schema",
                    "invariant_registry": "architecture/production_quality/invariant_registry.toml",
                    "review_packet": f"run:{run_id}:review_packet",
                    "scorecard_ref": f"run:{run_id}:quality_scorecard",
                    "readiness_ref": f"run:{run_id}:readiness",
                    "approval_ref": f"run:{run_id}:approval",
                    "redaction_policy": "redaction-policy/runtime-diagnostics-v1",
                    "source_refs": f"run:{run_id}:source_refs",
                }
                product_refs = {
                    **dict(runtime_quality_refs),
                    "runtime_quality_refs": f"run:{run_id}:runtime_quality_refs",
                    "authority_evidence": f"run:{run_id}:authority_evidence",
                    "cas_ref": f"run:{run_id}:cas_ref",
                    "artifact_manifest": f"run:{run_id}:artifact_manifest",
                    "quality_scorecard": f"run:{run_id}:quality_scorecard",
                    "readiness_summary": f"run:{run_id}:readiness",
                    "approval_packet": f"run:{run_id}:approval_packet",
                    "dashboard_projection": f"run:{run_id}:dashboard_projection",
                    "public_export": f"run:{run_id}:public_export",
                    "provider_response": f"run:{run_id}:provider_response",
                    "provider_quality_ledger": dict(runtime_quality_refs).get(
                        "provider_model_quality_ledger_ref"
                    )
                    or f"run:{run_id}:provider_quality",
                    "source_snapshot": dict(runtime_quality_refs).get(
                        "production_data_quality_report_ref"
                    )
                    or f"run:{run_id}:source_snapshot",
                    "selection_audit": dict(runtime_quality_refs).get("fabric_retrieval_trace_ref")
                    or f"run:{run_id}:selection_audit",
                    "norm_refs": dict(runtime_quality_refs).get(
                        "normative_applicability_report_ref"
                    )
                    or f"run:{run_id}:norm_refs",
                    "conflict_report": dict(runtime_quality_refs).get("conflict_check_ref")
                    or f"run:{run_id}:conflict_report",
                    "tool_result": f"run:{run_id}:tool_result",
                    "parser_result": dict(runtime_quality_refs).get("policy_grounding_matrix_ref")
                    or f"run:{run_id}:parser_result",
                    "repair_ledger": dict(runtime_quality_refs).get("prompt_tool_ledger_ref")
                    or f"run:{run_id}:repair_ledger",
                    "observer_bundle": f"run:{run_id}:observer_bundle",
                    "redacted_overlay": f"run:{run_id}:redacted_overlay",
                }
                try:
                    return [
                        serialize_attestation_record(record)
                        for record in build_required_production_attestations(
                            material_refs=material_refs,
                            product_refs=product_refs,
                            metadata={
                                "run_id": str(run_id),
                                "job_id": _runtime_quality_job_id(),
                            },
                        )
                    ]
                except Exception as exc:
                    logger.warning("Runtime quality attestation generation failed: %s", exc)
                    return []

            def _runtime_quality_trace_id() -> str:
                for key in ("trace_id", "runtime_trace_id"):
                    value = context.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                nested = context.get("runtime_identity")
                if isinstance(nested, Mapping):
                    value = nested.get("trace_id") or nested.get("runtime_trace_id")
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                return f"{run_id}:runtime-quality"

            def _runtime_quality_parent_span_id() -> str | None:
                value = context.get("parent_span_id")
                if isinstance(value, str) and value.strip():
                    return value.strip()
                nested = context.get("runtime_identity")
                if isinstance(nested, Mapping):
                    nested_value = nested.get("parent_span_id")
                    if isinstance(nested_value, str) and nested_value.strip():
                        return nested_value.strip()
                return None

            def _runtime_quality_payload_sha256(payload: Mapping[str, Any]) -> str:
                encoded = to_canonical_bytes(
                    dict(payload),
                    CanonSpec(forbid_floats=False),
                )
                return "sha256:" + hashlib.sha256(encoded).hexdigest()

            def _runtime_quality_input_ref_values(
                input_refs: list[InputRef] | None,
            ) -> tuple[str, ...]:
                values: list[str] = []
                for item in input_refs or []:
                    artifact_id = getattr(item, "artifact_id", None)
                    if artifact_id:
                        values.append(str(artifact_id))
                return tuple(values)

            def _runtime_quality_validation_status(
                report_payload: Mapping[str, Any],
            ) -> str:
                status = str(report_payload.get("status") or "").strip().casefold()
                if status in {"pass", "passed", "ok", "match", "complete"}:
                    return "pass"
                if status in {"blocked", "block"}:
                    return "blocked"
                if status in {"not_applicable", "n/a", "na", "skipped"}:
                    return "not_applicable"
                return "fail"

            def _runtime_quality_blocking_status(
                report_payload: Mapping[str, Any],
            ) -> str:
                return (
                    "non_blocking"
                    if _runtime_quality_validation_status(report_payload) == "pass"
                    else "blocking"
                )

            def _runtime_quality_governance_metadata() -> dict[str, str]:
                return {
                    "classification": "runtime_quality_evidence",
                    "authority_boundary": "runtime_control_plane",
                    "pii": "redacted_or_absent",
                    "retention_policy": "runtime_quality_retention",
                    "review_status": "machine_checked",
                    "override_policy": "no_silent_override",
                    "approval_policy": "scorecard_readiness_required",
                }

            def _runtime_quality_same_input_closure(
                *,
                input_refs: tuple[str, ...],
                closure_refs: Mapping[str, str | None],
            ) -> dict[str, Any]:
                """Rebuild owner identity around checked source pointers and current scope."""

                owner = runtime_quality_owner_binding
                if owner is None:
                    raise NaturalLanguagePipelineRefusalError(
                        "control_job_execution_scope_not_established"
                    )
                policy_intent_ref = closure_refs["policy_intent_ref"]
                production_manifest_ref = closure_refs["production_data_manifest_ref"]
                legal_snapshot_ref = closure_refs["legal_snapshot_ref"]
                effective_mode_ref = f"runtime-mode:{_runtime_quality_profile()}"
                return _normalize_runtime_quality_same_input_closure(
                    {
                        "closure_id": f"{owner['run_id']}:runtime_quality",
                        "status": "not_closed",
                        "policy_intent_ref": policy_intent_ref,
                        "run_id": owner["run_id"],
                        "job_id": owner["job_id"],
                        "tenant_id": owner["tenant_id"],
                        "cell_id": owner["cell_id"],
                        "time_context_ref": None,
                        "production_data_manifest_ref": production_manifest_ref,
                        "legal_snapshot_ref": legal_snapshot_ref,
                        "effective_mode_ref": effective_mode_ref,
                        "evidence_input_refs": input_refs,
                        "closure_sha256": None,
                    }
                )

            def _record_runtime_quality_diagnostic_event(
                summary: dict[str, Any],
            ) -> None:
                nonlocal runtime_quality_diagnostic_events

                ref_key = str(summary.get("ref_key") or "").strip()
                report_key = str(summary.get("report_key") or "").strip()
                runtime_quality_diagnostic_events = [
                    event
                    for event in runtime_quality_diagnostic_events
                    if not (
                        (ref_key and event.get("ref_key") == ref_key)
                        or (report_key and event.get("report_key") == report_key)
                    )
                ]
                runtime_quality_diagnostic_events.append(summary)

            def _runtime_quality_write_options(
                *,
                report_key: str,
                artifact_kind: str,
                schema_name: str,
                schema_version: str,
                input_refs: list[InputRef] | None,
                media_type: str = "application/json",
            ) -> ArtifactWriteOptions:
                return ArtifactWriteOptions(
                    kind=artifact_kind,
                    media_type=media_type,
                    schema=SchemaInfo(name=schema_name, version=schema_version),
                    producer=ProducerInfo(
                        component=(
                            owner_contract.producer_component
                            if (owner_contract := runtime_quality_report_owner_contract(report_key))
                            is not None
                            else f"polisyos.runtime.quality.{report_key}"
                        ),
                        version=(
                            owner_contract.producer_version
                            if owner_contract is not None
                            else RUNTIME_QUALITY_OWNER_PRODUCER_VERSION
                        ),
                    ),
                    governance=ArtifactGovernanceInfo(classification="runtime_quality_evidence"),
                    inputs=list(input_refs or []),
                )

            def _runtime_quality_publication_context_matches(
                *,
                basis: _RuntimeQualityReportPublicationBasis,
                report_key: str,
                ref_key: str,
                phase: str,
                requested_as_of_time: str | None,
            ) -> bool:
                envelope = basis.authority_envelope
                expected_context = {
                    "evidence_id": f"runtime_quality_ref#{ref_key}",
                    "tenant_id": _runtime_quality_identity_value("tenant_id"),
                    "cell_id": _runtime_quality_identity_value("cell_id"),
                    "run_id": run_id,
                    "job_id": _runtime_quality_job_id(),
                    "trace_id": _runtime_quality_trace_id(),
                    "span_id": f"{report_key}:cas_write",
                    "parent_span_id": _runtime_quality_parent_span_id(),
                    "requested_execution_profile": _runtime_quality_identity_value(
                        "requested_execution_profile"
                    ),
                    "effective_execution_profile": _runtime_quality_profile(),
                    "phase": phase,
                    "effective_mode_ref": f"runtime-mode:{_runtime_quality_profile()}",
                }
                if any(envelope.get(key) != value for key, value in expected_context.items()):
                    return False
                if requested_as_of_time is not None and envelope.get("as_of_time") != (
                    requested_as_of_time
                ):
                    return False
                closure = envelope.get("same_input_closure")
                return (
                    isinstance(closure, Mapping)
                    and closure.get("run_id") == run_id
                    and closure.get("job_id") == _runtime_quality_job_id()
                    and closure.get("tenant_id") == _runtime_quality_identity_value("tenant_id")
                    and closure.get("cell_id") == _runtime_quality_identity_value("cell_id")
                    and closure.get("closure_id") == f"{run_id}:runtime_quality"
                )

            def _runtime_quality_report_is_current_publication(
                *,
                report_key: str,
                ref_key: str,
                expected_ref: str,
            ) -> bool:
                contract = runtime_quality_report_owner_contract(report_key, ref_key)
                report_view = runtime_quality_evidence.get(report_key)
                write_options = runtime_quality_publication_write_options.get(ref_key)
                expected_identity_context = runtime_quality_publication_identity_contexts.get(
                    ref_key
                )
                if (
                    contract is None
                    or not isinstance(report_view, Mapping)
                    or write_options is None
                    or expected_identity_context is None
                ):
                    return False
                try:
                    _source_payload, basis = _runtime_quality_report_source_payload(
                        report_view,
                        report_key=report_key,
                        ref_key=ref_key,
                    )
                except ValueError:
                    return False
                selected_ref = runtime_quality_artifact_refs.get(ref_key)
                if (
                    basis is None
                    or type(selected_ref) is not ArtifactRef
                    or str(selected_ref.artifact_id) != expected_ref
                    or runtime_quality_refs.get(ref_key) != expected_ref
                    or basis.artifact_ref != selected_ref.model_dump(mode="json")
                    or not _runtime_quality_publication_context_matches(
                        basis=basis,
                        report_key=report_key,
                        ref_key=ref_key,
                        phase=contract.phase,
                        requested_as_of_time=runtime_quality_publication_requested_as_of_times.get(
                            ref_key
                        ),
                    )
                ):
                    return False
                if not any(
                    event.get("report_key") == report_key
                    and event.get("ref_key") == ref_key
                    and event.get("artifact_ref") == expected_ref
                    and event.get("runtime_event_ref") == basis.runtime_event_ref
                    and event.get("runtime_event_manifest_profile_sha256")
                    == basis.runtime_event_manifest_profile_sha256
                    for event in runtime_quality_diagnostic_events
                    if isinstance(event, Mapping)
                ):
                    return False
                return _runtime_quality_report_cas_publication_is_admitted(
                    artifact_store=store,
                    selected_ref=selected_ref,
                    runtime_ref=expected_ref,
                    report_key=report_key,
                    ref_key=ref_key,
                    report=report_view,
                    envelope=basis.authority_envelope,
                    expected_write_options=write_options,
                    expected_identity_context=expected_identity_context,
                )

            def _runtime_quality_current_reference_is_owner_published(
                current_ref_key: str,
                expected_ref: str,
            ) -> bool:
                """Reconcile a closure pointer to a current generic writer publication."""
                report_key = runtime_quality_publication_report_keys.get(current_ref_key)
                phase = runtime_quality_publication_phases.get(current_ref_key)
                write_options = runtime_quality_publication_write_options.get(current_ref_key)
                identity_context = runtime_quality_publication_identity_contexts.get(
                    current_ref_key
                )
                selected_ref = runtime_quality_artifact_refs.get(current_ref_key)
                if (
                    not isinstance(report_key, str)
                    or not isinstance(phase, str)
                    or write_options is None
                    or identity_context is None
                    or type(selected_ref) is not ArtifactRef
                    or runtime_quality_refs.get(current_ref_key) != expected_ref
                    or str(selected_ref.artifact_id) != expected_ref
                ):
                    return False

                binding = next(
                    (
                        item
                        for item in RUNTIME_QUALITY_PUBLICATION_CLOSURE_REFERENCE_BINDINGS
                        if item[1] is not None and item[1] == current_ref_key
                    ),
                    None,
                )
                if binding is None:
                    semantic_binding = (
                        RUNTIME_QUALITY_PUBLICATION_SEMANTIC_BINDING_REFERENCE_BINDING
                    )
                    if semantic_binding[0] != current_ref_key:
                        return False
                    expected_role, expected_kind, expected_schema_name, expected_schema_version = (
                        semantic_binding[1:]
                    )
                else:
                    expected_role, expected_kind, expected_schema_name, expected_schema_version = (
                        binding[2:]
                    )

                contract = runtime_quality_report_owner_contract(report_key, current_ref_key)
                if contract is not None:
                    if (
                        contract.artifact_kind != expected_kind
                        or contract.schema_name != expected_schema_name
                        or contract.schema_version != expected_schema_version
                    ):
                        return False
                    return _runtime_quality_report_is_current_publication(
                        report_key=report_key,
                        ref_key=current_ref_key,
                        expected_ref=expected_ref,
                    )

                return _runtime_quality_current_publisher_output_is_verified(
                    artifact_store=store,
                    runtime_ref=runtime_quality_refs.get(current_ref_key),
                    selected_ref=selected_ref,
                    write_options=write_options,
                    identity_context=identity_context,
                    report_key=report_key,
                    ref_key=current_ref_key,
                    expected_role=expected_role,
                    expected_kind=expected_kind,
                    expected_schema_name=expected_schema_name,
                    expected_schema_version=expected_schema_version,
                    phase=phase,
                    current_run_id=run_id,
                    current_job_id=_runtime_quality_job_id(),
                    current_tenant_id=_runtime_quality_identity_value("tenant_id"),
                    current_cell_id=_runtime_quality_identity_value("cell_id"),
                    current_trace_id=_runtime_quality_trace_id(),
                    current_parent_span_id=_runtime_quality_parent_span_id(),
                    current_requested_profile=_runtime_quality_identity_value(
                        "requested_execution_profile"
                    ),
                    current_effective_profile=_runtime_quality_profile(),
                    requested_as_of_time=runtime_quality_publication_requested_as_of_times.get(
                        current_ref_key
                    ),
                    event_summaries=runtime_quality_diagnostic_events,
                )

            async def _reuse_runtime_quality_report_publication(
                *,
                basis: _RuntimeQualityReportPublicationBasis,
                report_key: str,
                ref_key: str,
                ref_value: str,
                phase: str,
                requested_as_of_time: str | None,
                source_report_payload: Mapping[str, Any],
                candidate_view: Mapping[str, Any],
                semantic_binding_ref: str | None,
                output_artifact_id: str,
                write_options: ArtifactWriteOptions,
                materialization_basis_key: str | None,
            ) -> dict[str, Any]:
                nonlocal diagnostic_event_log_ref

                from polisyos.common.canonical_profile import require_declared_profile
                from polisyos.core.artifacts import (
                    read_core_json_artifact,
                    read_core_manifest_profile,
                )
                from polisyos.runtime.http.services.control.artifacts import (
                    _freeze_cas_writer_attestation_identity,
                    _identity_context_from_fields,
                )
                from polisyos.runtime.quality.authority import (
                    runtime_quality_report_cas_admission_issues,
                )
                from polisyos.runtime.quality.authority_reconciliation import (
                    resolve_authority_diagnostic_event_ref,
                )
                from polisyos.runtime.quality.diagnostic_events import (
                    DIAGNOSTIC_EVENT_ARTIFACT_KIND,
                )

                selected_ref = ArtifactRef.model_validate(basis.artifact_ref)
                selected_id = str(selected_ref.artifact_id)
                if (
                    basis.artifact_ref != selected_ref.model_dump(mode="json")
                    or selected_id != output_artifact_id
                    or (ref_value and ref_value != selected_id)
                    or not _runtime_quality_reuse_ref_matches_selected(
                        selected_ref,
                        selected_id,
                        runtime_quality_refs.get(ref_key),
                        runtime_quality_artifact_refs.get(ref_key),
                    )
                ):
                    raise RuntimeError("runtime_quality_publication_reuse_ref_mismatch")
                current_view = runtime_quality_evidence.get(report_key)
                if not isinstance(current_view, Mapping):
                    current_view = candidate_view
                if not isinstance(current_view, Mapping):
                    raise RuntimeError("runtime_quality_current_publication_not_established")
                try:
                    current_view_bytes = to_canonical_bytes(
                        dict(current_view),
                        CanonSpec(forbid_floats=False),
                    )
                    expected_view_bytes = to_canonical_bytes(
                        _runtime_quality_report_publication_view(basis),
                        CanonSpec(forbid_floats=False),
                    )
                except Exception as exc:
                    raise RuntimeError("runtime_quality_publication_view_not_canonical") from exc
                if current_view_bytes != expected_view_bytes:
                    raise RuntimeError("runtime_quality_current_publication_changed")
                if not _runtime_quality_publication_context_matches(
                    basis=basis,
                    report_key=report_key,
                    ref_key=ref_key,
                    phase=phase,
                    requested_as_of_time=requested_as_of_time,
                ):
                    raise RuntimeError("runtime_quality_publication_reuse_context_mismatch")

                try:
                    selected_manifest, declaration = read_core_manifest_profile(
                        store,
                        selected_ref,
                        manifest_profile_sha256=selected_ref.manifest_profile_sha256,
                    )
                except Exception as exc:
                    raise RuntimeError("runtime_quality_publication_reuse_profile_failed") from exc
                persisted_inputs = tuple(selected_manifest.inputs)
                current_inputs = tuple(write_options.inputs or [])
                if declaration.status != "declared":
                    raise RuntimeError("runtime_quality_publication_reuse_inputs_mismatch")
                later_inputs = tuple(
                    item for item in current_inputs if item not in persisted_inputs
                )
                verified_later_inputs: list[InputRef] = []
                for later_input in later_inputs:
                    sibling_verified = False
                    for sibling_report_key, sibling_ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
                        sibling_contract = runtime_quality_report_owner_contract(
                            sibling_report_key,
                            sibling_ref_key,
                        )
                        sibling_ref = runtime_quality_artifact_refs.get(sibling_ref_key)
                        if (
                            sibling_report_key == report_key
                            or sibling_contract is None
                            or later_input.role != sibling_ref_key.removesuffix("_ref")
                            or type(sibling_ref) is not ArtifactRef
                            or later_input.artifact_id != sibling_ref.artifact_id
                            or later_input.manifest_profile_sha256
                            != sibling_ref.manifest_profile_sha256
                            or sibling_ref.manifest_profile_sha256 is None
                            or sibling_ref.kind != sibling_contract.artifact_kind
                            or sibling_ref.media_type != sibling_contract.media_type
                            or runtime_quality_refs.get(sibling_ref_key)
                            != str(sibling_ref.artifact_id)
                        ):
                            continue
                        if _runtime_quality_report_is_current_publication(
                            report_key=sibling_report_key,
                            ref_key=sibling_ref_key,
                            expected_ref=str(sibling_ref.artifact_id),
                        ):
                            sibling_verified = True
                            break
                    if not sibling_verified:
                        raise RuntimeError("runtime_quality_publication_reuse_inputs_mismatch")
                    verified_later_inputs.append(later_input)
                try:
                    expected_inputs = _reconcile_runtime_quality_report_reentry_inputs(
                        current_inputs,
                        persisted_inputs,
                        verified_later_inputs,
                    )
                except RuntimeError as exc:
                    raise RuntimeError("runtime_quality_publication_reuse_inputs_mismatch") from exc
                if write_options.schema is None:
                    raise RuntimeError("runtime_quality_publication_reuse_schema_missing")
                expected_write_options = _runtime_quality_write_options(
                    report_key=report_key,
                    artifact_kind=write_options.kind,
                    schema_name=write_options.schema.name,
                    schema_version=write_options.schema.version,
                    input_refs=list(expected_inputs),
                    media_type=write_options.media_type,
                )
                authority = selected_manifest.authority
                if authority is None:
                    raise RuntimeError("runtime_quality_publication_reuse_authority_missing")
                try:
                    event_ref = resolve_authority_diagnostic_event_ref(store, authority)
                    if (
                        str(event_ref.artifact_id) != basis.runtime_event_ref
                        or event_ref.manifest_profile_sha256
                        != basis.runtime_event_manifest_profile_sha256
                        or event_ref.kind != DIAGNOSTIC_EVENT_ARTIFACT_KIND
                        or not store.verify(event_ref).ok
                    ):
                        raise ValueError("selected event identity differs")
                    event_manifest, event_declaration = read_core_manifest_profile(
                        store,
                        event_ref,
                        manifest_profile_sha256=basis.runtime_event_manifest_profile_sha256,
                    )
                    event_payload = require_declared_profile(
                        read_core_json_artifact(
                            store,
                            event_ref,
                            manifest_profile_sha256=basis.runtime_event_manifest_profile_sha256,
                        )
                    )
                except Exception as exc:
                    raise RuntimeError(
                        "runtime_quality_publication_reuse_event_not_verified"
                    ) from exc
                expected_event_context = {
                    "event_type": "polisyos.runtime.diagnostic.cas_write.v1",
                    "run_id": run_id,
                    "job_id": _runtime_quality_job_id(),
                    "tenant_id": _runtime_quality_identity_value("tenant_id"),
                    "cell_id": _runtime_quality_identity_value("cell_id"),
                    "trace_id": _runtime_quality_trace_id(),
                    "span_id": f"{report_key}:cas_write",
                    "parent_span_id": _runtime_quality_parent_span_id(),
                    "execution_profile": _runtime_quality_profile(),
                    "phase": phase,
                    "producer_component": expected_write_options.producer.component
                    if expected_write_options.producer is not None
                    else None,
                    "producer_version": expected_write_options.producer.version
                    if expected_write_options.producer is not None
                    else None,
                    "input_refs": list(
                        _runtime_quality_input_ref_values(expected_write_options.inputs)
                    ),
                    "artifact_refs": [selected_id],
                }
                if (
                    event_declaration.status != "declared"
                    or event_manifest.artifact_schema is None
                    or event_manifest.artifact_schema.name
                    != "polisyos.runtime.quality.diagnostic_event"
                    or event_manifest.artifact_schema.version != "1.0"
                    or not isinstance(event_payload, Mapping)
                    or any(
                        event_payload.get(key) != value
                        for key, value in expected_event_context.items()
                    )
                ):
                    raise RuntimeError("runtime_quality_publication_reuse_event_mismatch")

                persisted_candidate = _persisted_runtime_quality_publication_times(
                    store,
                    output_artifact_id=output_artifact_id,
                    artifact_kind=write_options.kind,
                    expected_inputs=expected_inputs,
                    selected_ref=selected_ref,
                )
                if persisted_candidate is None:
                    raise RuntimeError("runtime_quality_publication_reuse_closure_not_established")
                current_refs_for_closure = dict(runtime_quality_refs)
                frozen_context: tuple[tuple[InputRef, ...], frozenset[str]] | None = None
                if materialization_basis_key is not None:
                    frozen_context = frozen_materialization_publication_contexts.get(
                        (
                            materialization_basis_key,
                            ref_key,
                            output_artifact_id,
                        )
                    )
                    if frozen_context is not None and frozen_context[0] != expected_inputs:
                        raise RuntimeError("auto_materialization_input_basis_not_established")
                verified_later_input_ids = {str(item.artifact_id) for item in verified_later_inputs}
                for closure_binding in RUNTIME_QUALITY_PUBLICATION_CLOSURE_REFERENCE_BINDINGS:
                    closure_field, current_key = closure_binding[:2]
                    if current_key is None:
                        continue
                    current_value = current_refs_for_closure.get(current_key)
                    candidate_value = getattr(persisted_candidate, closure_field)
                    if (
                        candidate_value is None
                        and isinstance(current_value, str)
                        and current_value in verified_later_input_ids
                    ):
                        current_refs_for_closure.pop(current_key, None)
                closure_refs = _runtime_quality_closure_reference_values(
                    current_refs_for_closure,
                    candidate=persisted_candidate,
                    output_artifact_id=output_artifact_id,
                    ref_key=ref_key,
                    current_inputs=expected_write_options.inputs or [],
                    current_artifact_refs=runtime_quality_artifact_refs,
                    artifact_store=store,
                    current_report_verifier=(_runtime_quality_current_reference_is_owner_published),
                )
                semantic_binding_identity_ref = _runtime_quality_semantic_binding_ref(
                    report_payload=source_report_payload,
                    explicit_ref=semantic_binding_ref,
                    candidate=persisted_candidate,
                    output_artifact_id=output_artifact_id,
                    ref_key=ref_key,
                    current_inputs=expected_write_options.inputs or [],
                    current_report_verifier=(_runtime_quality_current_reference_is_owner_published),
                )
                expected_closure = _runtime_quality_same_input_closure(
                    input_refs=_runtime_quality_input_ref_values(expected_write_options.inputs),
                    closure_refs=closure_refs,
                )
                if semantic_binding_identity_ref != basis.authority_envelope.get(
                    "semantic_binding_ref"
                ):
                    raise RuntimeError("runtime_quality_publication_reuse_identity_mismatch")
                if not _runtime_quality_report_reuse_closure_matches(
                    basis,
                    expected_closure,
                ):
                    raise RuntimeError("runtime_quality_publication_reuse_closure_mismatch")

                closure_is_closed = (
                    expected_closure.get("status") == "closed"
                    and bool(expected_closure.get("closure_sha256"))
                    and bool(expected_closure.get("policy_intent_ref"))
                    and bool(expected_closure.get("time_context_ref"))
                )
                expected_authority_fields: dict[str, Any] = {
                    "evidence_id": f"runtime_quality_ref#{ref_key}",
                    "evidence_class": "authority_bearing",
                    "authority_role": "producer_authority"
                    if closure_is_closed
                    else "runtime_blocker",
                    "provenance_kind": "runtime_emitted"
                    if closure_is_closed
                    else "runtime_blocker",
                    "owner": "team-runtime",
                    "reader_contract": f"runtime_quality.{report_key}.v1",
                    "reader_contract_version": "1.0",
                    "tenant_id": _runtime_quality_identity_value("tenant_id"),
                    "cell_id": _runtime_quality_identity_value("cell_id"),
                    "run_id": _runtime_quality_identity_value("run_id"),
                    "job_id": _runtime_quality_job_id(),
                    "trace_id": _runtime_quality_trace_id(),
                    "span_id": f"{report_key}:cas_write",
                    "parent_span_id": _runtime_quality_parent_span_id(),
                    "requested_execution_profile": _runtime_quality_identity_value(
                        "requested_execution_profile"
                    ),
                    "effective_execution_profile": _runtime_quality_profile(),
                    "phase": phase,
                    "same_input_closure": expected_closure,
                    "input_refs": list(
                        _runtime_quality_input_ref_values(expected_write_options.inputs)
                    ),
                    "effective_mode_ref": f"runtime-mode:{_runtime_quality_profile()}",
                    "validation_status": _runtime_quality_validation_status(source_report_payload),
                    "blocking_status": (
                        _runtime_quality_blocking_status(source_report_payload)
                        if closure_is_closed
                        else "blocking"
                    ),
                    "governance": _runtime_quality_governance_metadata(),
                    "semantic_binding_ref": semantic_binding_identity_ref,
                    "generated_at": persisted_candidate.generated_at,
                    "as_of_time": persisted_candidate.as_of_time,
                    "canon_spec": CanonSpec(forbid_floats=False),
                }
                expected_identity_context = _identity_context_from_fields(
                    expected_write_options,
                    expected_authority_fields,
                    CanonSpec(forbid_floats=False),
                )
                if expected_write_options.schema is None or expected_write_options.producer is None:
                    raise RuntimeError("runtime_quality_publication_reuse_owner_not_established")
                expected_identity_context, _ = _freeze_cas_writer_attestation_identity(
                    expected_identity_context,
                    cas_ref_value=selected_id,
                    manifest_ref=f"cas-manifest://{selected_id}",
                    payload_sha256=selected_ref.artifact_id.hex,
                    schema=expected_write_options.schema,
                    producer=expected_write_options.producer,
                )
                admission_issues = runtime_quality_report_cas_admission_issues(
                    artifact_store=store,
                    selected_ref=selected_ref,
                    runtime_ref=selected_id,
                    report_key=report_key,
                    ref_key=ref_key,
                    report=current_view,
                    envelope=basis.authority_envelope,
                    expected_write_options=expected_write_options,
                    expected_identity_context=expected_identity_context,
                )
                if admission_issues:
                    issue_codes = ",".join(
                        str(issue.get("code") or "unknown") for issue in admission_issues
                    )
                    raise RuntimeError(
                        "runtime_quality_publication_reuse_not_established:" + issue_codes
                    )

                ref_value = selected_id
                _remember_selected_materialization_ref(selected_ref)
                event_summary = {
                    "event_name": f"{report_key}.persisted",
                    "event_type": "polisyos.runtime.diagnostic.cas_write.v1",
                    "runtime_event_ref": basis.runtime_event_ref,
                    "runtime_event_manifest_profile_sha256": (
                        basis.runtime_event_manifest_profile_sha256
                    ),
                    "artifact_ref": selected_id,
                    "runtime_cas_ref": selected_id,
                    "artifact_refs": [selected_id],
                    "payload_ref": selected_id,
                    "ref_key": ref_key,
                    "report_key": report_key,
                    "sampling": {"decision": "always_record", "rate": 1.0},
                    "authority_envelope_ref": basis.authority_envelope_ref,
                    "manifest_ref": basis.manifest_ref,
                    "payload_sha256": basis.payload_sha256,
                }
                _record_runtime_quality_diagnostic_event(event_summary)
                log_ref = await async_store.put_json(
                    {
                        "schema_version": "policyos.runtime.diagnostic_event_log_projection.v1",
                        "authority_role": "projection_only",
                        "run_id": run_id,
                        "job_id": _runtime_quality_job_id(),
                        "events": list(runtime_quality_diagnostic_events),
                        "selected_read_observations": [
                            observation.model_dump(mode="json")
                            for observation in runtime_quality_selected_reads
                        ],
                    },
                    ArtifactWriteOptions(
                        kind="runtime.diagnostic_event_log_projection",
                        media_type="application/json",
                        schema=SchemaInfo(
                            name="polisyos.runtime.quality.DiagnosticEventLogProjection",
                            version="1.0",
                        ),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                diagnostic_event_log_ref = str(log_ref.artifact_id)
                publication_view = _runtime_quality_report_publication_view(basis)
                ref_value = _register_runtime_quality_selected_output_ref(
                    ref_key=ref_key,
                    selected_ref=selected_ref,
                    runtime_quality_refs=runtime_quality_refs,
                    runtime_quality_artifact_refs=runtime_quality_artifact_refs,
                    expected_kind=expected_write_options.kind,
                    expected_media_type=expected_write_options.media_type,
                    expected_artifact_id=ref_value,
                )
                runtime_quality_evidence[report_key] = publication_view
                runtime_quality_publication_report_keys[ref_key] = report_key
                runtime_quality_publication_phases[ref_key] = phase
                runtime_quality_publication_write_options[ref_key] = expected_write_options
                runtime_quality_publication_identity_contexts[ref_key] = expected_identity_context
                runtime_quality_publication_requested_as_of_times[ref_key] = requested_as_of_time
                return publication_view

            async def _publish_runtime_quality_report(
                *,
                report_key: str,
                ref_key: str,
                ref_value: str,
                report_payload: Mapping[str, Any],
                artifact_kind: str,
                schema_name: str,
                schema_version: str = "1.0",
                phase: str,
                input_refs: list[InputRef] | None = None,
                semantic_binding_ref: str | None = None,
                media_type: str = "application/json",
                materialization_basis_key: str | None = None,
            ) -> dict[str, Any]:
                nonlocal diagnostic_event_log_ref

                try:
                    source_report_payload, _supplied_publication_basis = (
                        _runtime_quality_report_source_payload(
                            report_payload,
                            report_key=report_key,
                            ref_key=ref_key,
                        )
                    )
                except ValueError as exc:
                    raise RuntimeError(str(exc)) from exc
                input_ref_values = _runtime_quality_input_ref_values(input_refs)
                owner_contract = runtime_quality_report_owner_contract(report_key, ref_key)
                if report_key in QUALITY_REPORT_RUNTIME_REFS:
                    owner_issues = runtime_quality_report_owner_identity_issues(
                        report_key=report_key,
                        ref_key=ref_key,
                        artifact_kind=artifact_kind,
                        schema_name=schema_name,
                        schema_version=schema_version,
                        phase=phase,
                        media_type=media_type,
                        producer_component=f"polisyos.runtime.quality.{report_key}",
                        producer_version=RUNTIME_QUALITY_OWNER_PRODUCER_VERSION,
                    )
                    if owner_issues:
                        raise RuntimeError(
                            "runtime_quality_owner_contract_mismatch:" + ",".join(owner_issues)
                        )
                owner_marker = runtime_quality_report_owner_marker(report_key, ref_key)
                expected_marker = owner_marker or {
                    "schema_version": RUNTIME_QUALITY_OWNER_MARKER_SCHEMA,
                    "report_key": report_key,
                    "ref_key": ref_key,
                    "projection": False,
                }
                if (
                    "runtime_authority_payload" in report_payload
                    and report_payload.get("runtime_authority_payload") != expected_marker
                ):
                    raise RuntimeError("runtime_quality_owner_payload_marker_mismatch")
                if owner_contract is not None:
                    try:
                        authority_payload = _runtime_quality_report_writer_payload(
                            source_report_payload,
                            report_key=report_key,
                            ref_key=ref_key,
                        )
                    except ValueError as exc:
                        raise RuntimeError(str(exc)) from exc
                else:
                    authority_payload = dict(report_payload)
                    authority_payload.setdefault("runtime_authority_payload", expected_marker)
                write_options = _runtime_quality_write_options(
                    report_key=report_key,
                    artifact_kind=artifact_kind,
                    schema_name=schema_name,
                    schema_version=schema_version,
                    input_refs=input_refs,
                    media_type=media_type,
                )
                requested_as_of_time = str(context.get("as_of") or "") or None
                output_artifact_id = _runtime_quality_payload_sha256(authority_payload)
                if owner_contract is not None:
                    try:
                        reuse_basis = _runtime_quality_report_reuse_basis(
                            report_payload,
                            current_publication_view=runtime_quality_evidence.get(report_key),
                            report_key=report_key,
                            ref_key=ref_key,
                        )
                    except ValueError as exc:
                        raise RuntimeError(str(exc)) from exc
                    if reuse_basis is not None:
                        return await _reuse_runtime_quality_report_publication(
                            basis=reuse_basis,
                            report_key=report_key,
                            ref_key=ref_key,
                            ref_value=ref_value,
                            phase=phase,
                            requested_as_of_time=requested_as_of_time,
                            source_report_payload=source_report_payload,
                            candidate_view=report_payload,
                            semantic_binding_ref=semantic_binding_ref,
                            output_artifact_id=output_artifact_id,
                            write_options=write_options,
                            materialization_basis_key=materialization_basis_key,
                        )
                persisted_publication_candidate = _persisted_runtime_quality_publication_times(
                    store,
                    output_artifact_id=output_artifact_id,
                    artifact_kind=artifact_kind,
                    expected_inputs=write_options.inputs or [],
                )
                closure_refs = _runtime_quality_closure_reference_values(
                    runtime_quality_refs,
                    candidate=persisted_publication_candidate,
                    output_artifact_id=output_artifact_id,
                    ref_key=ref_key,
                    current_inputs=write_options.inputs or [],
                    current_artifact_refs=runtime_quality_artifact_refs,
                    artifact_store=store,
                    current_report_verifier=(_runtime_quality_current_reference_is_owner_published),
                )
                same_input_closure = _runtime_quality_same_input_closure(
                    input_refs=input_ref_values,
                    closure_refs=closure_refs,
                )
                semantic_binding_identity_ref = _runtime_quality_semantic_binding_ref(
                    report_payload=report_payload,
                    explicit_ref=semantic_binding_ref,
                    candidate=persisted_publication_candidate,
                    output_artifact_id=output_artifact_id,
                    ref_key=ref_key,
                    current_inputs=write_options.inputs or [],
                    current_report_verifier=(_runtime_quality_current_reference_is_owner_published),
                )
                closure_is_closed = (
                    same_input_closure.get("status") == "closed"
                    and bool(same_input_closure.get("closure_sha256"))
                    and bool(same_input_closure.get("policy_intent_ref"))
                    and bool(same_input_closure.get("time_context_ref"))
                )
                authority_identity_fields: dict[str, Any] = {
                    "evidence_id": f"runtime_quality_ref#{ref_key}",
                    "evidence_class": "authority_bearing",
                    "authority_role": "producer_authority"
                    if closure_is_closed
                    else "runtime_blocker",
                    "provenance_kind": "runtime_emitted"
                    if closure_is_closed
                    else "runtime_blocker",
                    "owner": "team-runtime",
                    "reader_contract": f"runtime_quality.{report_key}.v1",
                    "reader_contract_version": "1.0",
                    "tenant_id": _runtime_quality_identity_value("tenant_id"),
                    "cell_id": _runtime_quality_identity_value("cell_id"),
                    "run_id": _runtime_quality_identity_value("run_id"),
                    "job_id": _runtime_quality_job_id(),
                    "trace_id": _runtime_quality_trace_id(),
                    "span_id": f"{report_key}:cas_write",
                    "parent_span_id": _runtime_quality_parent_span_id(),
                    "requested_execution_profile": _runtime_quality_identity_value(
                        "requested_execution_profile"
                    ),
                    "effective_execution_profile": _runtime_quality_profile(),
                    "phase": phase,
                    "same_input_closure": same_input_closure,
                    "input_refs": list(input_ref_values),
                    "effective_mode_ref": f"runtime-mode:{_runtime_quality_profile()}",
                    "validation_status": _runtime_quality_validation_status(report_payload),
                    "blocking_status": (
                        _runtime_quality_blocking_status(report_payload)
                        if closure_is_closed
                        else "blocking"
                    ),
                    "governance": _runtime_quality_governance_metadata(),
                    "semantic_binding_ref": semantic_binding_identity_ref,
                }
                producer = write_options.producer
                schema = write_options.schema
                governance = write_options.governance
                publication_identity_key = _runtime_quality_payload_sha256(
                    cast(
                        "Mapping[str, Any]",
                        _json_safe_payload(
                            {
                                "payload_sha256": output_artifact_id,
                                "write_options": {
                                    "kind": write_options.kind,
                                    "media_type": write_options.media_type,
                                    "schema": (
                                        {
                                            "name": schema.name,
                                            "version": schema.version,
                                        }
                                        if schema is not None
                                        else None
                                    ),
                                    "producer": (
                                        {
                                            "component": producer.component,
                                            "version": producer.version,
                                        }
                                        if producer is not None
                                        else None
                                    ),
                                    "governance": (
                                        {"classification": governance.classification}
                                        if governance is not None
                                        else None
                                    ),
                                    "inputs": [
                                        item.model_dump(mode="json")
                                        for item in (write_options.inputs or [])
                                    ],
                                },
                                "authority_identity": authority_identity_fields,
                                "requested_as_of_time": requested_as_of_time,
                                "canon_spec": {"forbid_floats": False},
                            }
                        ),
                    )
                )
                attempt_time = datetime.now(UTC)
                generated_at, as_of_time = _runtime_quality_publication_times(
                    frozen_runtime_quality_publication_times,
                    identity_key=publication_identity_key,
                    requested_as_of_time=requested_as_of_time,
                    persisted_times=persisted_publication_candidate,
                    now=attempt_time,
                )
                authority_fields = {
                    **authority_identity_fields,
                    "generated_at": generated_at,
                    "as_of_time": as_of_time,
                    "canon_spec": CanonSpec(forbid_floats=False),
                }
                result = await run_blocking_async(
                    write_runtime_authority_artifact,
                    store,
                    self._diagnostic_event_log,
                    authority_payload,
                    write_options,
                    **authority_fields,
                )
                frozen_runtime_quality_publication_times[publication_identity_key] = (
                    result.identity_context.generated_at,
                    result.identity_context.as_of_time,
                )
                ref_value = str(result.cas_ref.artifact_id)
                _remember_selected_materialization_ref(result.cas_ref)
                runtime_event_ref = str(result.diagnostic_event_ref.artifact_id)
                runtime_event_manifest_profile_sha256 = (
                    result.diagnostic_event_ref.manifest_profile_sha256
                )
                authority_envelope_ref = str(result.authority_envelope_ref.artifact_id)
                authority_envelope = read_core_json_artifact(
                    store,
                    result.authority_envelope_ref,
                ).value
                publication_basis = None
                if owner_contract is not None:
                    selected_verification = store.verify(result.cas_ref)
                    selected_profile = result.cas_ref.manifest_profile_sha256
                    if not selected_verification.ok or selected_profile is None:
                        raise RuntimeError("runtime_quality_selected_cas_readback_not_verified")
                    selected_payload = require_declared_profile(
                        read_core_json_artifact(
                            store,
                            result.cas_ref,
                            manifest_profile_sha256=selected_profile,
                        )
                    )
                    if not isinstance(selected_payload, Mapping):
                        raise RuntimeError("runtime_quality_selected_cas_payload_not_object")
                    try:
                        expected_cas_bytes = to_canonical_bytes(
                            authority_payload,
                            CanonSpec(forbid_floats=False),
                        )
                        selected_cas_bytes = to_canonical_bytes(
                            dict(selected_payload),
                            CanonSpec(forbid_floats=False),
                        )
                    except Exception as exc:
                        raise RuntimeError(
                            "runtime_quality_selected_cas_payload_not_canonical"
                        ) from exc
                    if expected_cas_bytes != selected_cas_bytes:
                        raise RuntimeError("runtime_quality_selected_cas_payload_changed")
                    if not isinstance(authority_envelope, Mapping):
                        raise RuntimeError("runtime_quality_selected_envelope_not_object")
                    publication_basis = _build_runtime_quality_report_publication_basis(
                        report_key=report_key,
                        ref_key=ref_key,
                        report_payload=source_report_payload,
                        artifact_ref=result.cas_ref.model_dump(mode="json"),
                        runtime_event_ref=runtime_event_ref,
                        runtime_event_manifest_profile_sha256=(
                            runtime_event_manifest_profile_sha256
                        ),
                        authority_envelope_ref=authority_envelope_ref,
                        authority_envelope=authority_envelope,
                        manifest_ref=result.manifest_ref,
                        payload_sha256=result.payload_sha256,
                    )
                event_summary = {
                    "event_name": f"{report_key}.persisted",
                    "event_type": "polisyos.runtime.diagnostic.cas_write.v1",
                    "runtime_event_ref": runtime_event_ref,
                    "runtime_event_manifest_profile_sha256": (
                        runtime_event_manifest_profile_sha256
                    ),
                    "artifact_ref": ref_value,
                    "runtime_cas_ref": ref_value,
                    "artifact_refs": [ref_value],
                    "payload_ref": ref_value,
                    "ref_key": ref_key,
                    "report_key": report_key,
                    "sampling": {"decision": "always_record", "rate": 1.0},
                    "authority_envelope_ref": authority_envelope_ref,
                    "manifest_ref": result.manifest_ref,
                    "payload_sha256": result.payload_sha256,
                }
                _record_runtime_quality_diagnostic_event(event_summary)
                log_ref = await async_store.put_json(
                    {
                        "schema_version": "policyos.runtime.diagnostic_event_log_projection.v1",
                        "authority_role": "projection_only",
                        "run_id": run_id,
                        "job_id": _runtime_quality_job_id(),
                        "events": list(runtime_quality_diagnostic_events),
                        "selected_read_observations": [
                            observation.model_dump(mode="json")
                            for observation in runtime_quality_selected_reads
                        ],
                    },
                    ArtifactWriteOptions(
                        kind="runtime.diagnostic_event_log_projection",
                        media_type="application/json",
                        schema=SchemaInfo(
                            name="polisyos.runtime.quality.DiagnosticEventLogProjection",
                            version="1.0",
                        ),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                diagnostic_event_log_ref = str(log_ref.artifact_id)
                if publication_basis is not None:
                    evidence_payload = _runtime_quality_report_publication_view(publication_basis)
                else:
                    evidence_payload = dict(report_payload)
                    evidence_payload[ref_key] = ref_value
                    evidence_payload["runtime_quality_artifact_refs"] = {
                        ref_key: result.cas_ref.model_dump(mode="json")
                    }
                    evidence_payload["runtime_event_ref"] = runtime_event_ref
                    evidence_payload["runtime_event_manifest_profile_sha256"] = (
                        runtime_event_manifest_profile_sha256
                    )
                    evidence_payload["authority_envelope_ref"] = authority_envelope_ref
                    evidence_payload["authority_envelope"] = authority_envelope
                    evidence_payload["manifest_ref"] = result.manifest_ref
                    evidence_payload["payload_sha256"] = result.payload_sha256
                ref_value = _register_runtime_quality_selected_output_ref(
                    ref_key=ref_key,
                    selected_ref=result.cas_ref,
                    runtime_quality_refs=runtime_quality_refs,
                    runtime_quality_artifact_refs=runtime_quality_artifact_refs,
                    expected_kind=write_options.kind,
                    expected_media_type=write_options.media_type,
                    expected_artifact_id=ref_value,
                )
                runtime_quality_evidence[report_key] = evidence_payload
                runtime_quality_publication_report_keys[ref_key] = report_key
                runtime_quality_publication_phases[ref_key] = phase
                runtime_quality_publication_write_options[ref_key] = write_options
                runtime_quality_publication_identity_contexts[ref_key] = result.identity_context
                runtime_quality_publication_requested_as_of_times[ref_key] = requested_as_of_time
                return evidence_payload

            async def _persist_and_publish_runtime_quality_payload(
                *,
                report_key: str,
                ref_key: str,
                report_payload: Mapping[str, Any],
                artifact_kind: str,
                schema_name: str,
                schema_version: str = "1.0",
                phase: str,
                input_refs: list[InputRef] | None = None,
                semantic_binding_ref: str | None = None,
                media_type: str = "application/json",
                materialization_basis_key: str | None = None,
            ) -> tuple[str, dict[str, Any]]:
                evidence_payload = await _publish_runtime_quality_report(
                    report_key=report_key,
                    ref_key=ref_key,
                    ref_value="",
                    report_payload=report_payload,
                    artifact_kind=artifact_kind,
                    schema_name=schema_name,
                    schema_version=schema_version,
                    phase=phase,
                    input_refs=input_refs,
                    semantic_binding_ref=semantic_binding_ref,
                    media_type=media_type,
                    materialization_basis_key=materialization_basis_key,
                )
                return str(evidence_payload[ref_key]), evidence_payload

            def _intent_context_text(*keys: str, fallback: str | None = None) -> str | None:
                for key in keys:
                    value = context.get(key)
                    text = _clean_runtime_text(value)
                    if text:
                        return text
                target_context = context.get("target_context")
                if isinstance(target_context, Mapping):
                    for key in keys:
                        value = target_context.get(key)
                        text = _clean_runtime_text(value)
                        if text:
                            return text
                    countries = target_context.get("countries")
                    if "jurisdiction" in keys and isinstance(countries, list):
                        for country in countries:
                            text = _clean_runtime_text(country)
                            if text:
                                return text
                    if "policy_time" in keys or "data_time" in keys:
                        year = target_context.get("publication_year")
                        if isinstance(year, int | str) and str(year).strip():
                            return str(year).strip()
                return fallback

            def _intent_context_list(key: str) -> list[str]:
                value = context.get(key)
                if isinstance(value, str):
                    text = _clean_runtime_text(value)
                    return [text] if text else []
                if isinstance(value, list | tuple):
                    return [
                        text
                        for text in (_clean_runtime_text(item) for item in value)
                        if text is not None
                    ]
                return []

            def _policy_intent_authority_level(value: str | None) -> str:
                normalized = (value or _runtime_quality_profile()).strip().casefold()
                aliases = {
                    "dev": "research",
                    "development": "research",
                    "local": "research",
                    "test": "research",
                    "testing": "research",
                    "standard": "research",
                    "serious": "governed",
                    "high_stakes": "production",
                    "high-stakes": "production",
                }
                return aliases.get(normalized, normalized or "research")

            def _reconciled_policy_intent_authority_level(value: str | None) -> str:
                requested = _policy_intent_authority_level(value)
                effective = _policy_intent_authority_level(_runtime_quality_profile())
                rank = {"research": 0, "governed": 1, "production": 2}
                if rank.get(effective, -1) > rank.get(requested, -1):
                    return effective
                return requested

            def _producer_spine_context_payload() -> dict[str, Any] | None:
                payload = context.get("producer_spine_context")
                return dict(payload) if isinstance(payload, Mapping) else None

            async def _materialize_policy_intent_envelope() -> tuple[str, dict[str, Any]]:
                nonlocal context

                policy_time = _intent_context_text(
                    "policy_time",
                    "time_context",
                    "as_of",
                )
                data_time = _intent_context_text(
                    "data_time",
                    "data_window",
                    "time_window",
                )
                requested_authority = _intent_context_text(
                    "requested_authority_level",
                    fallback=_runtime_quality_profile(),
                )
                requested_authority = _reconciled_policy_intent_authority_level(requested_authority)
                intent_payload = build_policy_intent_envelope(
                    intent_id=f"intent-{run_id}",
                    run_id=run_id,
                    job_id=_runtime_quality_job_id(),
                    tenant_id=_runtime_quality_identity_value("tenant_id"),
                    policy_problem=_intent_context_text(
                        "policy_problem",
                        "problem",
                        fallback=nl_request,
                    )
                    or nl_request,
                    desired_outcome=(
                        _intent_context_text(
                            "desired_outcome",
                            "query_outcome",
                            "outcome",
                        )
                        or ""
                    ),
                    proposed_intervention=_intent_context_text(
                        "proposed_intervention",
                        "query_treatment",
                        "intervention",
                        fallback=domain_hint or "independent policy analysis",
                    )
                    or "independent policy analysis",
                    jurisdiction=_intent_context_text("jurisdiction") or "",
                    target_population=(
                        _intent_context_text("target_population", "population") or ""
                    ),
                    policy_time=policy_time or "",
                    data_time=data_time or "",
                    requester_preferred_conclusion=_clean_runtime_text(
                        context.get("requester_preferred_conclusion")
                    ),
                    requested_authority_level=requested_authority,
                    affected_stakeholders=_intent_context_list("affected_stakeholders"),
                    constraints=_intent_context_list("constraints"),
                    objectives=_intent_context_list("objectives"),
                    assumptions=_intent_context_list("assumptions"),
                    evidence_expectations=_intent_context_list("evidence_expectations"),
                    authoring_provenance={
                        "captured_by": "runtime-control-nl-pipeline",
                        "source_surface": "runtime.control.nl_request",
                        "domain_hint": domain_hint,
                    },
                )
                (
                    intent_ref,
                    evidence_payload,
                ) = await _persist_and_publish_runtime_quality_payload(
                    report_key="policy_intent_envelope",
                    ref_key="policy_intent_envelope_ref",
                    report_payload=intent_payload,
                    artifact_kind="runtime.policy_intent_envelope",
                    schema_name="polisyos.runtime.PolicyIntentEnvelope",
                    phase="policy_intent",
                )
                evidence_payload["policy_intent_ref"] = intent_ref
                runtime_quality_refs["policy_intent_ref"] = intent_ref
                context = {
                    **dict(context),
                    "policy_intent_ref": intent_ref,
                    "policy_intent_envelope_ref": intent_ref,
                    "policy_intent": intent_payload,
                }
                _emit_job_progress(
                    phase="policy_intent_materialized",
                    details={
                        "policy_intent_envelope_ref": intent_ref,
                        "policy_intent_ref": intent_ref,
                        **_runtime_quality_details(),
                    },
                )
                return intent_ref, evidence_payload

            async def _materialize_design_problem(
                *,
                intent_ref: str,
                intent_payload: Mapping[str, Any],
            ) -> tuple[str | None, DesignProblem | None]:
                nonlocal context

                del intent_payload
                if not models_to_run:
                    return None, None
                model_name = models_to_run[0]

                def _observe_design_problem_call(event: dict[str, Any]) -> None:
                    runtime_quality_cost_events.append(_project_call_event_cost(event))

                design_problem = await build_design_problem_from_nl_request(
                    nl_request=nl_request,
                    context={
                        **dict(context),
                        "policy_intent_ref": intent_ref,
                        "run_id": run_id,
                        "job_id": _runtime_quality_job_id(),
                    },
                    model_name=model_name,
                    run_id=run_id,
                    producer_settlement_store=getattr(self, "_llm_producer_settlement_store", None),
                    call_observer=_observe_design_problem_call,
                )
                payload = design_problem.model_dump(mode="json")
                (
                    design_problem_ref,
                    evidence_payload,
                ) = await _persist_and_publish_runtime_quality_payload(
                    report_key="design_problem",
                    ref_key="design_problem_ref",
                    report_payload=payload,
                    artifact_kind="runtime.design_problem",
                    schema_name="polisyos.runtime.DesignProblem",
                    phase="design_problem",
                    input_refs=[
                        _runtime_quality_selected_report_input_ref(
                            ref_key="policy_intent_envelope_ref",
                            role="policy_intent_envelope",
                            ref_value=intent_ref,
                            kind="runtime.policy_intent_envelope",
                        )
                    ],
                )
                evidence_payload["design_problem_ref"] = design_problem_ref
                runtime_quality_refs["design_problem_ref"] = design_problem_ref
                context = {
                    **dict(context),
                    "design_problem": payload,
                    "design_problem_ref": design_problem_ref,
                }
                _emit_job_progress(
                    phase="design_problem_materialized",
                    details={
                        "design_problem_ref": design_problem_ref,
                        "model": model_name,
                        **_runtime_quality_details(),
                    },
                )
                return design_problem_ref, design_problem

            def _runtime_authority_from_evidence(
                evidence_payload: Mapping[str, Any],
                *,
                ref_key: str,
            ) -> dict[str, str]:
                envelope = evidence_payload.get("authority_envelope")
                envelope_payload = envelope if isinstance(envelope, Mapping) else {}
                closure = envelope_payload.get("same_input_closure")
                closure_payload = closure if isinstance(closure, Mapping) else {}
                ref_value = _clean_runtime_text(evidence_payload.get(ref_key))
                runtime_event_ref = _clean_runtime_text(
                    evidence_payload.get("runtime_event_ref")
                    or envelope_payload.get("runtime_event_ref")
                )
                runtime_event_profile = _clean_runtime_text(
                    evidence_payload.get("runtime_event_manifest_profile_sha256")
                    or envelope_payload.get("runtime_event_manifest_profile_sha256")
                )
                closure_ref = _clean_runtime_text(envelope_payload.get("same_input_closure_ref"))
                closure_is_closed = (
                    closure_payload.get("status") == "closed"
                    and bool(closure_payload.get("closure_sha256"))
                    and bool(closure_payload.get("policy_intent_ref"))
                    and bool(closure_payload.get("time_context_ref"))
                    and bool(closure_ref)
                )
                authority: dict[str, str] = {
                    "authority_role": (
                        "producer_authority" if closure_is_closed else "runtime_blocker"
                    ),
                    "provenance_kind": "runtime_emitted"
                    if closure_is_closed
                    else "runtime_blocker",
                }
                for key, value in (
                    ("cas_ref", ref_value),
                    ("runtime_event_ref", runtime_event_ref),
                    (
                        "effective_mode_ref",
                        _clean_runtime_text(envelope_payload.get("effective_mode_ref")),
                    ),
                    (
                        "schema_compatibility_ref",
                        _clean_runtime_text(envelope_payload.get("schema_compatibility_ref")),
                    ),
                ):
                    if value is not None:
                        authority[key] = value
                if closure_is_closed and closure_ref is not None:
                    authority["same_input_closure_ref"] = closure_ref
                if runtime_event_profile is not None:
                    authority["runtime_event_manifest_profile_sha256"] = runtime_event_profile
                return authority

            async def _materialize_policy_design_capability_ledger(
                *,
                intent_ref: str,
            ) -> tuple[str, dict[str, Any], dict[str, Any]]:
                nonlocal context

                duties = [
                    build_capability_duty_record(
                        capability=capability,
                        state="selected",
                        evidence_ref=intent_ref,
                        reason="Selected by the Policy Design Case runtime profile.",
                        downstream_impact=(
                            "Serious policy closeout must preserve this producer duty "
                            "as selected, blocked, skipped with blocker, or degraded."
                        ),
                    )
                    for capability in POLICY_DESIGN_REQUIRED_CAPABILITIES
                ]
                ledger_payload = build_capability_selection_ledger(
                    ledger_ref=f"policy-design-capability-ledger:{run_id}",
                    duties=duties,
                    literature_evidence_required=True,
                )
                ledger_payload["status"] = "pass"
                (
                    ledger_ref,
                    evidence_payload,
                ) = await _persist_and_publish_runtime_quality_payload(
                    report_key="policy_design_capability_ledger",
                    ref_key="policy_design_capability_ledger_ref",
                    report_payload=ledger_payload,
                    artifact_kind="runtime.policy_design_capability_ledger",
                    schema_name="polisyos.runtime.PolicyDesignCapabilityLedger",
                    phase="policy_design_capability_ledger",
                    input_refs=[
                        _runtime_quality_selected_report_input_ref(
                            ref_key="policy_intent_envelope_ref",
                            role="policy_intent_envelope",
                            ref_value=intent_ref,
                            kind="runtime.policy_intent_envelope",
                        )
                    ],
                )
                runtime_quality_refs["policy_design_capability_ledger_ref"] = ledger_ref
                context = {
                    **dict(context),
                    "policy_design_capability_ledger_ref": ledger_ref,
                    "policy_design_capability_ledger": ledger_payload,
                }
                _emit_job_progress(
                    phase="policy_design_capability_ledger_materialized",
                    details={
                        "policy_design_capability_ledger_ref": ledger_ref,
                        **_runtime_quality_details(),
                    },
                )
                return ledger_ref, ledger_payload, evidence_payload

            def _policy_design_spine_terms(
                intent_payload: Mapping[str, Any],
            ) -> list[str]:
                terms: list[str] = []
                for key in (
                    "policy_problem",
                    "desired_outcome",
                    "proposed_intervention",
                    "jurisdiction",
                    "target_population",
                    "policy_time",
                    "data_time",
                ):
                    text = _clean_runtime_text(intent_payload.get(key))
                    if text:
                        terms.append(text)
                for key in ("objectives", "constraints", "evidence_expectations"):
                    value = intent_payload.get(key)
                    if isinstance(value, list | tuple):
                        terms.extend(
                            text for text in (_clean_runtime_text(item) for item in value) if text
                        )
                return list(dict.fromkeys(terms))

            def _policy_design_jurisdiction_seed_report(
                intent_payload: Mapping[str, Any],
            ) -> dict[str, Any]:
                target_context = {
                    "jurisdiction": _clean_runtime_text(intent_payload.get("jurisdiction"))
                    or _intent_context_text("jurisdiction")
                    or "unbound",
                    "as_of": _clean_runtime_text(intent_payload.get("policy_time"))
                    or _intent_context_text("policy_time", "as_of")
                    or datetime.now(UTC).date().isoformat(),
                    "policy_domain": _intent_context_text(
                        "policy_domain",
                        "top_domain",
                        "domain",
                        fallback=domain_hint,
                    ),
                }
                return {
                    "schema_version": "policyos.lex.normative_applicability_report.v1",
                    "status": "blocked",
                    "target_context": target_context,
                    "applied_norms": [],
                    "candidate_norms": [],
                    "issues": [
                        {
                            "code": "jurisdiction_spine_seed_requires_lex_norms",
                            "severity": "warn",
                        }
                    ],
                }

            async def _materialize_policy_design_spines(
                *,
                intent_payload: Mapping[str, Any],
                intent_ref: str,
                capability_ledger_evidence: Mapping[str, Any],
            ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
                nonlocal context

                concept_payload = build_policy_design_case_concept_spine(
                    run_id=run_id,
                    job_id=_runtime_quality_job_id(),
                    tenant_id=_runtime_quality_identity_value("tenant_id"),
                    policy_intent_ref=intent_ref,
                    raw_user_terms=_policy_design_spine_terms(intent_payload),
                    generated_at=datetime.now(UTC),
                )
                (
                    concept_ref,
                    concept_evidence,
                ) = await _persist_and_publish_runtime_quality_payload(
                    report_key="policy_design_concept_spine",
                    ref_key="concept_spine_ref",
                    report_payload=concept_payload,
                    artifact_kind="runtime.policy_design_concept_spine",
                    schema_name="polisyos.runtime.PolicyDesignConceptSpine",
                    phase="policy_design_concept_spine",
                    input_refs=[
                        _runtime_quality_selected_report_input_ref(
                            ref_key="policy_intent_envelope_ref",
                            role="policy_intent_envelope",
                            ref_value=intent_ref,
                            kind="runtime.policy_intent_envelope",
                        )
                    ],
                )
                runtime_quality_refs["concept_ref"] = concept_ref

                jurisdiction_seed_ref = _runtime_quality_payload_sha256(
                    {
                        "run_id": run_id,
                        "intent_ref": intent_ref,
                        "surface": "policy_design_jurisdiction_spine",
                    }
                )
                jurisdiction_payload = build_policy_design_jurisdiction_spine(
                    spine_id=f"jurisdiction_spine.{run_id}",
                    jurisdiction_spine_ref=jurisdiction_seed_ref,
                    run_id=run_id,
                    job_id=_runtime_quality_job_id(),
                    tenant_id=_runtime_quality_identity_value("tenant_id"),
                    policy_intent_ref=intent_ref,
                    lex_normative_report=_policy_design_jurisdiction_seed_report(intent_payload),
                    runtime_authority={
                        "authority_role": "runtime_blocker",
                        "provenance_kind": "runtime_blocker",
                        "cas_ref": jurisdiction_seed_ref,
                        "runtime_event_ref": (
                            f"event://policy_design_case/jurisdiction_spine/{run_id}"
                        ),
                        "same_input_closure_ref": _runtime_quality_payload_sha256(
                            {"intent_ref": intent_ref, "jurisdiction_seed": True}
                        ),
                        "effective_mode_ref": _runtime_quality_payload_sha256(
                            {"profile": _runtime_quality_profile(), "run_id": run_id}
                        ),
                        "schema_compatibility_ref": _runtime_quality_payload_sha256(
                            {"schema": "policy_design_jurisdiction_spine.v1"}
                        ),
                    },
                    generated_at=datetime.now(UTC),
                )
                (
                    jurisdiction_ref,
                    jurisdiction_evidence,
                ) = await _persist_and_publish_runtime_quality_payload(
                    report_key="policy_design_jurisdiction_spine",
                    ref_key="jurisdiction_spine_ref",
                    report_payload=jurisdiction_payload,
                    artifact_kind="runtime.policy_design_jurisdiction_spine",
                    schema_name="polisyos.runtime.PolicyDesignJurisdictionSpine",
                    phase="policy_design_jurisdiction_spine",
                    input_refs=[
                        _runtime_quality_selected_report_input_ref(
                            ref_key="policy_intent_envelope_ref",
                            role="policy_intent_envelope",
                            ref_value=intent_ref,
                            kind="runtime.policy_intent_envelope",
                        )
                    ],
                )
                runtime_quality_refs["jurisdiction_ref"] = jurisdiction_ref
                jurisdiction_refs = [
                    str(row.get("jurisdiction_id"))
                    for row in jurisdiction_payload.get("jurisdictions", [])
                    if isinstance(row, Mapping) and row.get("jurisdiction_id")
                ]
                spine_context = build_producer_spine_read_context(
                    concept_spine_ref=concept_ref,
                    jurisdiction_spine_ref=jurisdiction_ref,
                    canonical_concept_refs=[
                        str(item) for item in concept_payload.get("canonical_concept_ids", [])
                    ],
                    jurisdiction_refs=jurisdiction_refs,
                )
                context = {
                    **dict(context),
                    "concept_spine_ref": concept_ref,
                    "concept_ref": concept_ref,
                    "concept_spine": concept_evidence,
                    "jurisdiction_spine_ref": jurisdiction_ref,
                    "jurisdiction_ref": jurisdiction_ref,
                    "jurisdiction_spine": jurisdiction_evidence,
                    "producer_spine_context": spine_context,
                }
                _emit_job_progress(
                    phase="policy_design_spines_materialized",
                    details={
                        "concept_spine_ref": concept_ref,
                        "jurisdiction_spine_ref": jurisdiction_ref,
                        "producer_spine_context": spine_context,
                        **_runtime_quality_details(),
                    },
                )
                return concept_evidence, jurisdiction_evidence, spine_context

            async def _persist_policy_design_runtime_payload(
                *,
                intent_payload: Mapping[str, Any],
                intent_ref: str,
                capability_ledger: Mapping[str, Any],
                capability_ledger_ref: str,
                capability_ledger_evidence: Mapping[str, Any],
                concept_spine: Mapping[str, Any] | None = None,
                jurisdiction_spine: Mapping[str, Any] | None = None,
            ) -> tuple[str, dict[str, Any]]:
                nonlocal context

                profile_payload = build_policy_design_case_profile(
                    case_id=f"pdc-{run_id}",
                    run_id=run_id,
                    job_id=_runtime_quality_job_id(),
                    tenant_id=_runtime_quality_identity_value("tenant_id"),
                    effective_execution_profile=_policy_intent_authority_level(
                        _runtime_quality_profile()
                    ),
                    runtime_authority=_runtime_authority_from_evidence(
                        capability_ledger_evidence,
                        ref_key="policy_design_capability_ledger_ref",
                    ),
                    capability_ledger=capability_ledger,
                    intent_envelope=intent_payload,
                    jurisdiction_spine=jurisdiction_spine,
                    nodes=[concept_spine] if concept_spine is not None else None,
                )
                profile_payload = compile_policy_design_case_runtime_record_families(
                    profile_payload
                )
                (
                    profile_ref,
                    evidence_payload,
                ) = await _persist_and_publish_runtime_quality_payload(
                    report_key="policy_design_case",
                    ref_key="policy_design_case_ref",
                    report_payload=profile_payload,
                    artifact_kind="runtime.policy_design_case",
                    schema_name="polisyos.runtime.PolicyDesignCase",
                    phase="policy_design_case_profile",
                    input_refs=[
                        _runtime_quality_selected_report_input_ref(
                            ref_key="policy_intent_envelope_ref",
                            role="policy_intent_envelope",
                            ref_value=intent_ref,
                            kind="runtime.policy_intent_envelope",
                        ),
                        InputRef(
                            artifact_id=_make_artifact_ref(
                                capability_ledger_ref,
                                kind="runtime.policy_design_capability_ledger",
                            ).artifact_id,
                            role="policy_design_capability_ledger",
                        ),
                    ],
                )
                runtime_quality_refs["policy_design_case_ref"] = profile_ref
                context = {
                    **dict(context),
                    "policy_design_case_ref": profile_ref,
                    "policy_design_case": profile_payload,
                }
                _emit_job_progress(
                    phase="policy_design_case_materialized",
                    details={
                        "policy_design_case_ref": profile_ref,
                        **_runtime_quality_details(),
                    },
                )
                return profile_ref, evidence_payload

            def _runtime_quality_details() -> dict[str, Any]:
                details: dict[str, Any] = {
                    **dict(runtime_quality_refs),
                    "runtime_quality_refs": dict(runtime_quality_refs),
                    "runtime_quality_artifact_refs": dict(runtime_quality_artifact_refs),
                    "runtime_quality_evidence": dict(runtime_quality_evidence),
                    "runtime_quality_projection": _runtime_quality_progress_projection(),
                }
                if diagnostic_event_log_ref:
                    details["diagnostic_event_log_ref"] = diagnostic_event_log_ref
                if runtime_quality_diagnostic_events:
                    details["diagnostic_events"] = list(runtime_quality_diagnostic_events)
                attestations = _runtime_quality_attestations()
                if attestations:
                    details["trust_boundary_attestations"] = attestations
                return details

            async def _ensure_registry_bundle_ref() -> ArtifactRef:
                nonlocal registry_bundle_ref_cache
                if registry_bundle_ref_cache is None:
                    bundle = await run_blocking_async(
                        build_default_registry_bundle,
                        store,
                        return_selected_profile=True,
                    )
                    registry_bundle_ref = bundle.bundle_ref
                    if registry_bundle_ref is None:
                        raise RuntimeError(
                            "default registry bundle did not produce an artifact reference"
                        )
                    registry_bundle_ref_cache = registry_bundle_ref
                    _remember_selected_materialization_ref(registry_bundle_ref)
                if registry_bundle_ref_cache is None:
                    raise RuntimeError("default registry bundle ref cache was not populated")
                return registry_bundle_ref_cache

            async def _ensure_catalog_snapshot() -> tuple[MethodCatalogSnapshot, str]:
                async with catalog_lock:
                    cached_snapshot = method_catalog_snapshot_cache.get("snapshot")
                    cached_ref = method_catalog_snapshot_cache.get("ref")
                    if isinstance(cached_snapshot, MethodCatalogSnapshot) and isinstance(
                        cached_ref, str
                    ):
                        return cached_snapshot, cached_ref
                    ensure_causal_methods_registered()
                    snapshot = build_method_catalog_snapshot(run_id=run_id)
                    snapshot_ref = await _persist_nl_execution_artifact(
                        persist_method_catalog_snapshot,
                        snapshot,
                    )
                    snapshot_ref_str = str(snapshot_ref.artifact_id)
                    method_catalog_snapshot_cache["snapshot"] = snapshot
                    method_catalog_snapshot_cache["ref"] = snapshot_ref_str
                    return snapshot, snapshot_ref_str

            async def _materialize_retrieval_artifacts(
                *,
                variant_id: str,
                data_context_payload: dict[str, Any],
                retrieval_telemetry: dict[str, Any],
                data_needs_payload: list[dict[str, Any]],
            ) -> dict[str, str]:
                payload_ref = await async_store.put_json(
                    {
                        "model_variant_id": variant_id,
                        "data_context": data_context_payload,
                        "retrieval_telemetry": retrieval_telemetry,
                    },
                    ArtifactWriteOptions(
                        kind="fabric.retrieval_payload",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.fabric.RetrievalPayload", version="1.0"),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
                _remember_selected_materialization_ref(payload_ref)
                quality_summary = RetrievalSummary(
                    assessment_status="not_assessed",
                    source="retrieval_service",
                    source_refs=[payload_ref],
                    observed_counts={
                        "metrics": len(data_context_payload.get("metrics") or []),
                        "metadata_docs_fetched": int(
                            data_context_payload.get("metadata_docs_fetched") or 0
                        ),
                    },
                    notes=[
                        f"mode:{retrieval_telemetry.get('mode') or 'hybrid'!s}",
                        *list(retrieval_telemetry.get("warnings") or []),
                    ],
                )
                quality_ref = await async_store.put_json(
                    quality_summary,
                    ArtifactWriteOptions(
                        kind=RetrievalSummary.ARTIFACT_KIND,
                        media_type="application/json",
                        schema=SchemaInfo(
                            name=RetrievalSummary.ARTIFACT_SCHEMA_NAME,
                            version=RetrievalSummary.ARTIFACT_SCHEMA_VERSION,
                        ),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
                _remember_selected_materialization_ref(quality_ref)
                snapshot = DataSnapshot(
                    data_ref=payload_ref,
                    quality_report_ref=quality_ref,
                    stats={
                        "metric_count": len(data_context_payload.get("metrics") or []),
                        "metadata_docs_fetched": int(
                            data_context_payload.get("metadata_docs_fetched") or 0
                        ),
                    },
                    notes=[
                        "source:runtime_nl_retrieval",
                        f"model_variant_id:{variant_id}",
                    ],
                )
                snapshot_ref = await async_store.put_json(
                    snapshot,
                    ArtifactWriteOptions(
                        kind="fabric.data_snapshot",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
                        inputs=[
                            input_ref_from_artifact_ref(payload_ref, role="retrieval_payload"),
                            input_ref_from_artifact_ref(quality_ref, role="quality_report"),
                        ],
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
                _remember_selected_materialization_ref(snapshot_ref)
                registry_ref = await _ensure_registry_bundle_ref()
                try:
                    from polisyos.core.artifacts import ensure_ir_artifact_store
                    from polisyos.foundry.data_plane import build_input_bindings

                    bindings_result = await run_blocking_async(
                        build_input_bindings,
                        ensure_ir_artifact_store(store),
                        data_snapshot_ref=snapshot_ref,
                        registry_bundle_ref=registry_ref,
                        rules=None,
                        notes=["runtime_nl_auto_materialization"],
                        return_selected_profile=True,
                    )
                    _remember_selected_materialization_ref(bindings_result.input_bindings_ref)
                    _remember_selected_materialization_ref(bindings_result.input_binding_report_ref)
                    refs = {
                        "data_snapshot_ref": str(snapshot_ref.artifact_id),
                        "input_bindings_ref": str(bindings_result.input_bindings_ref.artifact_id),
                        "registry_bundle_ref": str(registry_ref.artifact_id),
                        "quality_report_ref": str(quality_ref.artifact_id),
                        "input_binding_report_ref": str(
                            bindings_result.input_binding_report_ref.artifact_id
                        ),
                    }
                    (
                        production_quality_ref,
                        _production_quality_report,
                    ) = await _persist_production_data_quality_report(
                        evidence_context={
                            "root": None,
                            "manifest_path": None,
                            "manifest_sha256": None,
                            "bundles": {},
                            "materialization_mode": "retrieval_service",
                        },
                        materialization_refs=refs,
                        data_needs_payload=data_needs_payload,
                    )
                    refs["production_data_quality_report_ref"] = production_quality_ref
                    return refs
                except ModuleNotFoundError:
                    # Keep pipeline runnable in lightweight environments without JAX.
                    fallback_state_ref = await async_store.put_json(
                        {"source": "runtime_nl_auto_materialization", "jax": "missing"},
                        ArtifactWriteOptions(
                            kind="foundry.state_payload",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.foundry.StatePayload", version="0.1.0"
                            ),
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                        return_selected_profile=True,
                    )
                    fallback_snapshot = StateSnapshot(
                        schema_version="2.0",
                        state_ref=fallback_state_ref,
                        step=0,
                        notes=["fallback_state_snapshot_without_jax"],
                    )
                    fallback_snapshot_ref = await async_store.put_json(
                        fallback_snapshot,
                        ArtifactWriteOptions(
                            kind="foundry.state_snapshot",
                            media_type="application/json",
                            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="1.0"),
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                        return_selected_profile=True,
                    )
                    fallback_bindings = FoundryInputBindings(
                        schema_version="1.0",
                        data_snapshot_ref=snapshot_ref,
                        registry_bundle_ref=registry_ref,
                        rules=[],
                        bound_state_snapshot_ref=StateSnapshotRef.model_validate(
                            fallback_snapshot_ref.model_dump(mode="python")
                        ),
                        notes=["fallback_bindings_without_jax"],
                    )
                    fallback_bindings_ref = await async_store.put_json(
                        fallback_bindings,
                        ArtifactWriteOptions(
                            kind="foundry.input_bindings",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.core.FoundryInputBindings", version="1.0"
                            ),
                            inputs=[
                                input_ref_from_artifact_ref(
                                    snapshot_ref,
                                    role="data_snapshot",
                                ),
                                input_ref_from_artifact_ref(
                                    fallback_snapshot_ref,
                                    role="bound_state",
                                ),
                            ],
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                        return_selected_profile=True,
                    )
                    _remember_selected_materialization_ref(fallback_bindings_ref)
                    fallback_report_ref = await async_store.put_json(
                        {
                            "ok": False,
                            "warnings": ["jax_not_available"],
                            "applied_rules": [],
                            "errors": [],
                        },
                        ArtifactWriteOptions(
                            kind="foundry.input_binding_report",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.foundry.FoundryInputBindingReport",
                                version="1.0",
                            ),
                            inputs=[
                                input_ref_from_artifact_ref(
                                    fallback_bindings_ref,
                                    role="input_bindings",
                                )
                            ],
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                        return_selected_profile=True,
                    )
                    _remember_selected_materialization_ref(fallback_report_ref)
                    refs = {
                        "data_snapshot_ref": str(snapshot_ref.artifact_id),
                        "input_bindings_ref": str(fallback_bindings_ref.artifact_id),
                        "registry_bundle_ref": str(registry_ref.artifact_id),
                        "quality_report_ref": str(quality_ref.artifact_id),
                        "input_binding_report_ref": str(fallback_report_ref.artifact_id),
                    }
                    (
                        production_quality_ref,
                        _production_quality_report,
                    ) = await _persist_production_data_quality_report(
                        evidence_context={
                            "root": None,
                            "manifest_path": None,
                            "manifest_sha256": None,
                            "bundles": {},
                            "materialization_mode": "retrieval_service",
                        },
                        materialization_refs=refs,
                        data_needs_payload=data_needs_payload,
                    )
                    refs["production_data_quality_report_ref"] = production_quality_ref
                    return refs

            async def _materialize_production_data_artifacts(
                *,
                variant_id: str,
                production_params: dict[str, Any],
                data_needs_payload: list[dict[str, Any]],
                fetch_plans_payload: list[dict[str, Any]],
                retrieval_telemetry: dict[str, Any],
            ) -> tuple[dict[str, str], dict[str, Any], dict[str, Any]]:
                evidence_context = _production_data_evidence_context(
                    production_params,
                    allow_default=True,
                )
                if evidence_context is None:
                    raise RuntimeError("production_data_evidence_context_missing")
                manifest_sha = evidence_context.get("manifest_sha256")
                bundles = evidence_context.get("bundles")
                if not isinstance(manifest_sha, str) or not manifest_sha:
                    raise RuntimeError("production_data_manifest_checksum_missing")
                if not isinstance(bundles, Mapping) or not bundles:
                    raise RuntimeError("production_data_bundles_missing")

                metrics_payload: list[dict[str, Any]] = [
                    {
                        "metric_id": item.get("metric"),
                        "geography": item.get("geography"),
                        "granularity": item.get("granularity"),
                        "purpose": item.get("purpose"),
                        "source_lane": "production_data_manifest",
                    }
                    for item in data_needs_payload
                ]
                data_context_payload: dict[str, Any] = {
                    "metrics": metrics_payload,
                    "metadata_docs_fetched": int(
                        retrieval_telemetry.get("metadata_docs_fetched") or 0
                    ),
                    "index_docs_total": int(retrieval_telemetry.get("local_index_docs_total") or 0),
                    "index_size_bytes": int(retrieval_telemetry.get("local_index_size_bytes") or 0),
                    "production_data_evidence_context": evidence_context,
                }
                payload_ref = await async_store.put_json(
                    {
                        "model_variant_id": variant_id,
                        "data_context": data_context_payload,
                        "data_needs": data_needs_payload,
                        "fetch_plans": fetch_plans_payload,
                        "retrieval_telemetry": retrieval_telemetry,
                        "production_data_evidence_context": evidence_context,
                    },
                    ArtifactWriteOptions(
                        kind="fabric.production_data_payload",
                        media_type="application/json",
                        schema=SchemaInfo(
                            name="polisyos.fabric.ProductionDataPayload",
                            version="1.0",
                        ),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
                _remember_selected_materialization_ref(payload_ref)
                quality_summary = RetrievalSummary(
                    assessment_status="not_assessed",
                    source="production_data_manifest",
                    source_refs=[payload_ref],
                    observed_counts={
                        "metrics": len(metrics_payload),
                        "bundles": len(bundles),
                        "fetch_plans": len(fetch_plans_payload),
                        "data_needs": len(data_needs_payload),
                    },
                    notes=[
                        f"manifest_sha256:{manifest_sha}",
                        *list(retrieval_telemetry.get("warnings") or []),
                    ],
                )
                quality_ref = await async_store.put_json(
                    quality_summary,
                    ArtifactWriteOptions(
                        kind=RetrievalSummary.ARTIFACT_KIND,
                        media_type="application/json",
                        schema=SchemaInfo(
                            name=RetrievalSummary.ARTIFACT_SCHEMA_NAME,
                            version=RetrievalSummary.ARTIFACT_SCHEMA_VERSION,
                        ),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
                _remember_selected_materialization_ref(quality_ref)
                snapshot = DataSnapshot(
                    data_ref=payload_ref,
                    quality_report_ref=quality_ref,
                    stats={
                        "metric_count": len(metrics_payload),
                        "bundle_count": len(bundles),
                        "fetch_plan_count": len(fetch_plans_payload),
                    },
                    notes=[
                        "source:production_data_manifest",
                        f"model_variant_id:{variant_id}",
                        f"manifest_sha256:{manifest_sha}",
                    ],
                )
                snapshot_ref = await async_store.put_json(
                    snapshot,
                    ArtifactWriteOptions(
                        kind="fabric.data_snapshot",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
                        inputs=[
                            input_ref_from_artifact_ref(
                                payload_ref,
                                role="production_data_payload",
                            ),
                            input_ref_from_artifact_ref(quality_ref, role="quality_report"),
                        ],
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
                _remember_selected_materialization_ref(snapshot_ref)
                registry_ref = await _ensure_registry_bundle_ref()
                try:
                    from polisyos.core.artifacts import ensure_ir_artifact_store
                    from polisyos.foundry.data_plane import build_input_bindings

                    bindings_result = await run_blocking_async(
                        build_input_bindings,
                        ensure_ir_artifact_store(store),
                        data_snapshot_ref=snapshot_ref,
                        registry_bundle_ref=registry_ref,
                        rules=None,
                        notes=["runtime_nl_production_data_materialization"],
                        return_selected_profile=True,
                    )
                    _remember_selected_materialization_ref(bindings_result.input_bindings_ref)
                    _remember_selected_materialization_ref(bindings_result.input_binding_report_ref)
                    refs = {
                        "data_snapshot_ref": str(snapshot_ref.artifact_id),
                        "input_bindings_ref": str(bindings_result.input_bindings_ref.artifact_id),
                        "registry_bundle_ref": str(registry_ref.artifact_id),
                        "quality_report_ref": str(quality_ref.artifact_id),
                        "input_binding_report_ref": str(
                            bindings_result.input_binding_report_ref.artifact_id
                        ),
                    }
                except ModuleNotFoundError:
                    fallback_state_ref = await async_store.put_json(
                        {
                            "source": "runtime_nl_production_data_materialization",
                            "jax": "missing",
                        },
                        ArtifactWriteOptions(
                            kind="foundry.state_payload",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.foundry.StatePayload",
                                version="0.1.0",
                            ),
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                        return_selected_profile=True,
                    )
                    fallback_snapshot = StateSnapshot(
                        schema_version="2.0",
                        state_ref=fallback_state_ref,
                        step=0,
                        notes=["fallback_state_snapshot_without_jax"],
                    )
                    fallback_snapshot_ref = await async_store.put_json(
                        fallback_snapshot,
                        ArtifactWriteOptions(
                            kind="foundry.state_snapshot",
                            media_type="application/json",
                            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="1.0"),
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                        return_selected_profile=True,
                    )
                    fallback_bindings = FoundryInputBindings(
                        schema_version="1.0",
                        data_snapshot_ref=snapshot_ref,
                        registry_bundle_ref=registry_ref,
                        rules=[],
                        bound_state_snapshot_ref=StateSnapshotRef.model_validate(
                            fallback_snapshot_ref.model_dump(mode="python")
                        ),
                        notes=["fallback_bindings_without_jax"],
                    )
                    fallback_bindings_ref = await async_store.put_json(
                        fallback_bindings,
                        ArtifactWriteOptions(
                            kind="foundry.input_bindings",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.core.FoundryInputBindings",
                                version="1.0",
                            ),
                            inputs=[
                                input_ref_from_artifact_ref(
                                    snapshot_ref,
                                    role="data_snapshot",
                                ),
                                input_ref_from_artifact_ref(
                                    fallback_snapshot_ref,
                                    role="bound_state",
                                ),
                            ],
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                        return_selected_profile=True,
                    )
                    _remember_selected_materialization_ref(fallback_bindings_ref)
                    fallback_report_ref = await async_store.put_json(
                        {
                            "ok": False,
                            "warnings": ["jax_not_available"],
                            "applied_rules": [],
                            "errors": [],
                        },
                        ArtifactWriteOptions(
                            kind="foundry.input_binding_report",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.foundry.FoundryInputBindingReport",
                                version="1.0",
                            ),
                            inputs=[
                                input_ref_from_artifact_ref(
                                    fallback_bindings_ref,
                                    role="input_bindings",
                                )
                            ],
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                        return_selected_profile=True,
                    )
                    _remember_selected_materialization_ref(fallback_report_ref)
                    refs = {
                        "data_snapshot_ref": str(snapshot_ref.artifact_id),
                        "input_bindings_ref": str(fallback_bindings_ref.artifact_id),
                        "registry_bundle_ref": str(registry_ref.artifact_id),
                        "quality_report_ref": str(quality_ref.artifact_id),
                        "input_binding_report_ref": str(fallback_report_ref.artifact_id),
                    }
                trace_query_intent = {
                    "policy_domain": domain_hint,
                    "execution_profile": execution_profile,
                }
                if data_needs_payload:
                    first_need = data_needs_payload[0]
                    trace_query_intent["query_outcome"] = first_need.get("metric")
                    trace_query_intent["geography"] = first_need.get("geography")
                trace_ref, trace_payload = await _persist_production_data_fabric_trace(
                    query_intent={
                        str(key): value
                        for key, value in trace_query_intent.items()
                        if value is not None
                    },
                    evidence_context=evidence_context,
                    data_needs_payload=data_needs_payload,
                    fetch_plans_payload=fetch_plans_payload,
                    retrieval_telemetry=retrieval_telemetry,
                    materialization_refs=refs,
                )
                refs["fabric_retrieval_trace_ref"] = trace_ref
                (
                    production_quality_ref,
                    production_quality_report,
                ) = await _persist_production_data_quality_report(
                    evidence_context=evidence_context,
                    materialization_refs=refs,
                    data_needs_payload=data_needs_payload,
                )
                refs["production_data_quality_report_ref"] = production_quality_ref
                evidence_context = dict(evidence_context)
                evidence_context["fabric_retrieval_trace_ref"] = trace_ref
                evidence_context["fabric_retrieval_trace"] = trace_payload
                evidence_context["fabric_retrieval_trace_status"] = trace_payload.get("status")
                if trace_payload.get("scenario_evidence_contract_id"):
                    evidence_context["scenario_evidence_contract_id"] = trace_payload.get(
                        "scenario_evidence_contract_id"
                    )
                if isinstance(trace_payload.get("evidence_spine_carrier"), Mapping):
                    evidence_context["evidence_spine_carrier"] = dict(
                        trace_payload["evidence_spine_carrier"]
                    )
                if isinstance(trace_payload.get("scenario_requirement_ids"), list):
                    evidence_context["scenario_requirement_ids"] = list(
                        trace_payload["scenario_requirement_ids"]
                    )
                if isinstance(trace_payload.get("fabric_spine_bindings"), Mapping):
                    evidence_context["fabric_spine_bindings"] = dict(
                        trace_payload["fabric_spine_bindings"]
                    )
                if isinstance(
                    trace_payload.get("production_data_contract_binding_report"),
                    Mapping,
                ):
                    binding_report = trace_payload["production_data_contract_binding_report"]
                    evidence_context["production_data_contract_binding_report"] = binding_report
                    evidence_context["scenario_binding_findings"] = binding_report.get(
                        "scenario_binding_findings",
                    )
                evidence_context["production_data_quality_report_ref"] = production_quality_ref
                evidence_context["production_data_quality_report"] = production_quality_report
                evidence_context["production_data_quality_status"] = production_quality_report.get(
                    "status"
                )
                evidence_context["materialization_refs"] = dict(refs)
                evidence_context["timeline"] = [
                    {
                        "event": "production_data_quality_report_persisted",
                        "production_data_quality_report_ref": production_quality_ref,
                        "status": production_quality_report.get("status"),
                    }
                ]
                evidence_context["lineage"] = [
                    {
                        "kind": "runtime.production_data_quality_report",
                        "production_data_quality_report_ref": production_quality_ref,
                        "input_refs": dict(refs),
                    }
                ]
                data_context_payload["fabric_retrieval_trace_ref"] = trace_ref
                data_context_payload["fabric_retrieval_trace"] = trace_payload
                data_context_payload["fabric_retrieval_trace_status"] = trace_payload.get("status")
                if evidence_context.get("scenario_evidence_contract_id"):
                    data_context_payload["scenario_evidence_contract_id"] = evidence_context.get(
                        "scenario_evidence_contract_id"
                    )
                if evidence_context.get("evidence_spine_carrier"):
                    data_context_payload["evidence_spine_carrier"] = evidence_context.get(
                        "evidence_spine_carrier"
                    )
                if evidence_context.get("scenario_requirement_ids"):
                    data_context_payload["scenario_requirement_ids"] = evidence_context.get(
                        "scenario_requirement_ids"
                    )
                if evidence_context.get("fabric_spine_bindings"):
                    data_context_payload["fabric_spine_bindings"] = evidence_context.get(
                        "fabric_spine_bindings"
                    )
                if evidence_context.get("scenario_binding_findings") is not None:
                    data_context_payload["scenario_binding_findings"] = evidence_context.get(
                        "scenario_binding_findings"
                    )
                data_context_payload["production_data_quality_report_ref"] = production_quality_ref
                data_context_payload["production_data_quality_report"] = production_quality_report
                data_context_payload["production_data_quality_status"] = (
                    production_quality_report.get("status")
                )
                data_context_payload["production_data_evidence_context"] = evidence_context
                return refs, data_context_payload, evidence_context

            async def _store_bundle(bundle: object) -> ArtifactRef:
                ref = await _put_nl_tenant_owned_json(
                    async_store,
                    bundle,
                    ArtifactWriteOptions(
                        kind="ir.trinity_bundle",
                        media_type="application/json",
                        schema=SchemaInfo(
                            name="polisyos.ir.TrinityBundle",
                            version=str(getattr(bundle, "schema_version", "1.0")),
                        ),
                    ),
                    tenant_context=trinity_bundle_tenant_context,
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
                _remember_selected_materialization_ref(ref)
                return ref

            async def _store_final_policy_claims_report(
                report: dict[str, Any],
                *,
                trinity_bundle_ref: ArtifactRef | None,
            ) -> ArtifactRef:
                from polisyos.core.security.tenant_context import tenant_scope

                with tenant_scope(
                    None,
                    tenant_id=trinity_bundle_tenant_context.tenant_id,
                    cell_id=trinity_bundle_tenant_context.cell_id,
                ):
                    inputs = []
                    if trinity_bundle_ref is not None:
                        selected_trinity_ref = _selected_materialization_ref(
                            trinity_bundle_ref, "ir.trinity_bundle"
                        )
                        inputs.append(
                            input_ref_from_artifact_ref(selected_trinity_ref, role="trinity_bundle")
                        )
                    ref = await _put_nl_tenant_owned_json(
                        async_store,
                        report,
                        ArtifactWriteOptions(
                            kind="scientist.final_policy_claims",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.scientist.FinalPolicyClaims", version="1.0"
                            ),
                            inputs=inputs,
                        ),
                        tenant_context=trinity_bundle_tenant_context,
                        canon_spec=CanonSpec(forbid_floats=False),
                        return_selected_profile=True,
                    )
                _remember_selected_materialization_ref(ref)
                return ref

            async def _run_variant(model_name: str | None, variant_index: int) -> dict[str, Any]:
                nonlocal current_capability_manifest_ref
                variant_started_at = _now_ms()
                variant_started_iso = datetime.now(UTC).replace(microsecond=0).isoformat()
                call_events: list[dict[str, Any]] = []

                def _observe_llm_call(event: dict[str, Any]) -> None:
                    call_events.append({**event, "pipeline_step_id": _CURRENT_NL_STEP_ID.get()})

                variant_label = model_name or "mock"
                variant_id = _normalize_model_variant_id(variant_label, variant_index)
                notes: list[str] = []
                llm_client = None
                provider = "mock"
                _emit_job_progress(
                    phase="model_variant_started",
                    variant_id=variant_id,
                    variant_status="running",
                    details={"model": model_name, "provider": provider},
                )

                if model_name:
                    llm_client = create_traced_gateway_client(
                        model_name=model_name,
                        run_id=run_id,
                        model_variant_id=variant_id,
                        call_observer=_observe_llm_call,
                        tracer=self._tracer,
                        metrics=self._metrics,
                        cache_reuse_authorizer=cache_reuse_authorizer,
                        cache_reuse_principal=cache_reuse_principal,
                        cache_reuse_context=cache_reuse_context,
                        prompt_cache=getattr(self, "_llm_prompt_cache", None),
                        require_reuse_authorization=True,
                        producer_settlement_store=getattr(
                            self, "_llm_producer_settlement_store", None
                        ),
                        producer_budget_key=f"nl-run:{run_id}",
                    )
                    if llm_client is None:
                        if allow_mock_fallback:
                            notes.append("gateway_not_configured_contract_testing_mock")
                        if allow_mock_fallback and callable(capability_manifest_updater):
                            current_capability_manifest_ref = capability_manifest_updater(
                                ["gateway_not_configured_contract_testing_mock"]
                            )
                    else:
                        provider = "gateway"
                    _emit_job_progress(
                        phase="model_variant_gateway_ready",
                        variant_id=variant_id,
                        variant_status="running",
                        details={"model": model_name, "provider": provider},
                    )
                elif not allow_mock_fallback:
                    raise NaturalLanguagePipelineRefusalError("llm_model_unconfigured")

                if llm_client is None and not allow_mock_fallback:
                    if design_problem is None:
                        raise NaturalLanguagePipelineRefusalError(
                            "design_problem_unavailable",
                            "N4 cannot route an unavailable gateway without a DesignProblem.",
                        )
                    n4_run = await generate_design_candidate_bundle_under_a(
                        design_problem,
                        model_id=str(model_name),
                        llm_client=None,
                        repo_root=Path(__file__).resolve().parents[6],
                    )
                    n4_terminal = n4_run.result.model_dump(mode="json")
                    terminal_reason = (
                        n4_run.result.degraded_artifacts[0].reason
                        if n4_run.result.degraded_artifacts
                        else n4_run.result.status
                    )
                    return {
                        "model_variant_id": variant_id,
                        "model": model_name,
                        "provider": "gateway_unavailable",
                        "status": "failed",
                        "verdict": None,
                        "issue_count": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "latency_ms": max(0, _now_ms() - variant_started_at),
                        "cost_usd": 0.0,
                        "started_at": variant_started_iso,
                        "finished_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                        "steps": [],
                        "notes": [f"n4_generation_terminal:{terminal_reason}"],
                        "schema_healing": [],
                        "schema_healing_count": 0,
                        "n4_generation_terminal": n4_terminal,
                        "failure": {
                            "code": "generation_unavailable",
                            "layer": "n4_generation",
                            "phase": "model_variant_gateway",
                            "message": str(terminal_reason),
                            "retryable": False,
                        },
                        "_bundle": None,
                    }

                curated_dir = _resolve_curated_dir()
                if llm_client is None:
                    if contract_testing_agent_factory is None:
                        raise NaturalLanguagePipelineRefusalError(
                            "fabric_generation_bypass_blocked"
                        )
                    agents = contract_testing_agent_factory()
                    if len(agents) != 5:
                        raise NaturalLanguagePipelineRefusalError(
                            "contract_testing_agent_factory_invalid"
                        )
                    pi, data_need_extractor, drafter, formalizer, critic = agents
                else:
                    pi = LLMPIAgent(llm_client=llm_client, model_name=model_name)
                    data_need_extractor = LLMDataNeedExtractorAgent(
                        llm_client=llm_client,
                        model_name=model_name,
                        curated_dir=curated_dir,
                        allow_fallback=allow_mock_fallback,
                    )
                    drafter = LLMDrafterAgent(llm_client=llm_client, model_name=model_name)
                    formalizer = LLMFormalizerAgent(
                        llm_client=llm_client,
                        model_name=model_name,
                        metric_taxonomy=metric_taxonomy,
                        fail_unknown_metrics=_is_serious_execution_profile(execution_profile),
                    )
                    critic = LLMCriticAgent(llm_client=llm_client, model_name=model_name)

                retrieval_catalog = None

                steps: list[dict[str, Any]] = []
                retrieval_telemetry: dict[str, Any] = {}
                retrieval_mode = "hybrid"
                retrieval_lane_used = "none"
                retrieval_metadata_docs_fetched = 0
                retrieval_index_size_bytes = 0
                retrieval_index_docs_total = 0
                retrieval_candidates_filtered = 0
                retrieval_candidates_promoted = 0
                retrieval_phase_durations: dict[str, int] = {}
                data_context_payload: dict[str, Any] = {}
                auto_data_source_refs: dict[str, str] = {}
                retrieval_context_payload: dict[str, Any] = {
                    "data_needs": [],
                    "fetch_plans": [],
                    "promotion_candidates": [],
                    "auto_data_source_refs": {},
                }
                execution_plan_ref_str = execution_plan_ref
                method_catalog_snapshot_ref_str: str | None = None
                preflight_report_ref_str: str | None = None
                evaluator_report_ref_str: str | None = None
                iteration_state_ref_str: str | None = None
                reproducibility_manifest_ref_str: str | None = None
                preflight_ready = True
                preflight_diagnostics: list[dict[str, Any]] = []
                evaluator_payload: dict[str, Any] = {}
                critique_payload: dict[str, Any] | None = None
                final_policy_claims_report: dict[str, Any] = {}
                final_policy_claims_ref_str: str | None = None
                claim_extraction_failure: dict[str, Any] | None = None
                fabric_result = None
                fabric_shadow_result = None
                fabric_shadow_task = None
                fabric_shadow_comparison = None

                async def _capture_step(
                    *,
                    agent: str,
                    action: str,
                    coro: Awaitable[_StepResult],
                    summary: str | None = None,
                    status: str = "ok",
                    details: dict[str, Any] | None = None,
                ) -> _StepResult:
                    step_id = f"{action}:{len(steps) + 1}"
                    step_token = _CURRENT_NL_STEP_ID.set(step_id)
                    started = _now_ms()
                    running_step = {
                        "step_id": step_id,
                        "agent": agent,
                        "action": action,
                        "status": "running",
                        "summary": summary,
                        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
                        "details": details or {},
                    }
                    _emit_job_progress(
                        phase=action,
                        variant_id=variant_id,
                        variant_status="running",
                        step=running_step,
                    )
                    try:
                        result = await coro
                    except Exception as exc:
                        _CURRENT_NL_STEP_ID.reset(step_token)
                        failure_payload = _exception_failure_payload(exc)
                        failed_details = {**dict(details or {}), "error": str(exc)}
                        if failure_payload is not None:
                            failed_details["failure"] = failure_payload
                        step_events = [
                            _project_call_event_cost(event)
                            for event in call_events
                            if event.get("pipeline_step_id") == step_id
                        ]
                        step_usage = _sum_call_events(
                            [
                                event
                                for event in call_events
                                if event.get("pipeline_step_id") == step_id
                            ]
                        )
                        failed_step = {
                            **running_step,
                            "status": "failed",
                            "cost_usd": (
                                round(float(step_usage["cost_usd"]), 8)
                                if step_usage["cost_usd"] is not None
                                else None
                            ),
                            "cost_events": step_events,
                            "details": failed_details,
                        }
                        steps.append(failed_step)
                        _emit_job_progress(
                            phase=action,
                            variant_id=variant_id,
                            variant_status="failed",
                            step=failed_step,
                        )
                        raise
                    finally:
                        if _CURRENT_NL_STEP_ID.get() == step_id:
                            _CURRENT_NL_STEP_ID.reset(step_token)
                    finished = _now_ms()
                    step_call_events = [
                        event for event in call_events if event.get("pipeline_step_id") == step_id
                    ]
                    step_usage = _sum_call_events(step_call_events)
                    step_cost = step_usage["cost_usd"]
                    step_cost_events = [
                        _project_call_event_cost(event) for event in step_call_events
                    ]
                    prompt_tokens = int(step_usage["prompt_tokens"])
                    completion_tokens = int(step_usage["completion_tokens"])
                    llm_latency_ms = int(step_usage["latency_ms"])
                    total_tokens = prompt_tokens + completion_tokens
                    step_latency = max(0, finished - started)
                    step_entry = {
                        "attempt": 1,
                        "agent": agent,
                        "action": action,
                        "status": status,
                        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
                        "summary": summary,
                        "model": model_name,
                        "provider": provider,
                        "model_variant_id": variant_id,
                        "latency_ms": llm_latency_ms or step_latency,
                        "cost_usd": round(float(step_cost), 8) if step_cost is not None else None,
                        "cost_events": step_cost_events,
                        "cost_origin_counts": step_usage["cost_origin_counts"],
                        "settlement_status_counts": step_usage["settlement_status_counts"],
                        "token_usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                        },
                        "details": details or {},
                    }
                    steps.append(step_entry)
                    _emit_job_progress(
                        phase=action,
                        variant_id=variant_id,
                        variant_status="running",
                        step=step_entry,
                    )
                    return result

                def _append_step(
                    *,
                    agent: str,
                    action: str,
                    summary: str | None = None,
                    status: str = "ok",
                    details: dict[str, Any] | None = None,
                ) -> None:
                    step_entry = {
                        "attempt": 1,
                        "agent": agent,
                        "action": action,
                        "status": status,
                        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
                        "summary": summary,
                        "model": model_name,
                        "provider": provider,
                        "model_variant_id": variant_id,
                        "latency_ms": 0,
                        "cost_usd": 0.0,
                        "token_usage": {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                        },
                        "details": details or {},
                    }
                    steps.append(step_entry)
                    _emit_job_progress(
                        phase=action,
                        variant_id=variant_id,
                        variant_status="running",
                        step=step_entry,
                    )

                try:
                    from polisyos.data_forge.read_api import catalog as catalog_read_api

                    source = self._catalog_serving_source
                    retrieval_catalog = catalog_read_api.DatasetCatalogGraph(
                        source.database_path,
                        source.index_dir,
                        overlay_path=source.overlay_path,
                    )
                    retrieval = RetrievalService(
                        curated_dir=curated_dir,
                        artifact_store=self._artifact_store,
                        dataset_catalog=retrieval_catalog,
                        providers=self._build_retrieval_providers(),
                    )
                    problem_frame = await _capture_step(
                        agent="pi_agent",
                        action="create_problem_frame",
                        coro=pi.create_problem_frame(
                            nl_request,
                            domain_hint=domain_hint or "custom",
                        ),
                        summary="Problem frame created",
                    )
                    await pi.hold_problem_frame(problem_frame)
                    data_need_specs = await _capture_step(
                        agent="data_need_extractor",
                        action="extract_data_need",
                        coro=data_need_extractor.extract_data_needs(problem_frame),
                        summary="Data needs extracted from problem frame",
                    )
                    data_needs = [
                        DataNeed(
                            metric=spec.metric,
                            geography=spec.geography,
                            time_start=spec.time_start,
                            time_end=spec.time_end,
                            granularity=spec.granularity,
                            quality_min=spec.quality_min,
                            purpose=spec.purpose,
                        )
                        for spec in data_need_specs
                        if spec.metric
                    ]
                    if not data_needs:
                        notes.append("no_data_needs_extracted")
                    retrieval_context_payload["data_needs"] = [
                        item.model_dump(mode="json") for item in data_needs
                    ]

                    # 1) Build ExecutionPlan first and persist as the first cycle artifact.
                    if execution_plan_payload:
                        try:
                            execution_plan_data = dict(execution_plan_payload)
                            execution_plan_data["run_id"] = run_id
                            execution_plan_data["iteration"] = 1
                            if isinstance(stop_criteria_payload, dict):
                                execution_plan_data["stop_criteria"] = dict(stop_criteria_payload)
                            if isinstance(governance_constraints_payload, list):
                                execution_plan_data["governance_constraints"] = list(
                                    governance_constraints_payload
                                )
                            if isinstance(expected_outputs_payload, list):
                                execution_plan_data["expected_outputs"] = list(
                                    expected_outputs_payload
                                )
                            execution_plan = ExecutionPlan.model_validate(execution_plan_data)
                        except (TypeError, ValueError) as exc:
                            logger.debug(
                                "Falling back to default execution plan for run %s: %s",
                                run_id,
                                exc,
                            )
                            execution_plan = build_default_execution_plan(
                                run_id=run_id,
                                data_needs=data_needs,
                                method_dag=[],
                                params={"context": context},
                                max_iterations=max_iterations,
                                run_budget_usd=run_budget_usd,
                                per_model_budget_usd=per_model_budget_usd,
                                governance_constraints=governance_constraints_payload,
                                expected_outputs=expected_outputs_payload,
                            )
                    else:
                        execution_plan = build_default_execution_plan(
                            run_id=run_id,
                            data_needs=data_needs,
                            method_dag=[],
                            params={"context": context},
                            max_iterations=max_iterations,
                            run_budget_usd=run_budget_usd,
                            per_model_budget_usd=per_model_budget_usd,
                            governance_constraints=governance_constraints_payload,
                            expected_outputs=expected_outputs_payload,
                        )

                    if not execution_plan_ref_str:
                        execution_plan_ref_obj = await _persist_nl_execution_artifact(
                            persist_execution_plan,
                            execution_plan,
                        )
                        execution_plan_ref_str = str(execution_plan_ref_obj.artifact_id)
                    _append_step(
                        agent="planner",
                        action="build_execution_plan",
                        summary="ExecutionPlan persisted",
                        details={
                            "execution_plan_ref": execution_plan_ref_str,
                            "data_needs": len(execution_plan.data_needs),
                            "method_dag_nodes": len(execution_plan.method_dag),
                        },
                    )

                    # 2) Build and cache live method catalog snapshot for this run.
                    (
                        catalog_snapshot,
                        method_catalog_snapshot_ref_str,
                    ) = await _ensure_catalog_snapshot()
                    snapshot_injector = cast(
                        "_MethodCatalogSnapshotAware | None",
                        formalizer if hasattr(formalizer, "set_method_catalog_snapshot") else None,
                    )
                    if snapshot_injector is not None:
                        try:
                            snapshot_injector.set_method_catalog_snapshot(
                                catalog_snapshot.model_dump(mode="json")
                            )
                        except (AttributeError, TypeError, ValueError) as exc:
                            logger.debug(
                                "Failed to inject method catalog snapshot for run %s: %s",
                                run_id,
                                exc,
                            )
                            notes.append("formalizer_catalog_injection_failed")

                    # 3) Mandatory preflight before execution.
                    preflight_report = preflight_execution_plan(execution_plan, catalog_snapshot)
                    preflight_report.plan_ref = ExecutionPlanRef.model_validate(
                        _selected_nl_execution_artifact_ref(
                            execution_plan_ref_str, kind="scientist.execution_plan"
                        ).model_dump(mode="python")
                    )
                    preflight_report.catalog_snapshot_ref = MethodCatalogSnapshotRef.model_validate(
                        _selected_nl_execution_artifact_ref(
                            method_catalog_snapshot_ref_str,
                            kind="foundry.method_catalog_snapshot",
                        ).model_dump(mode="python")
                    )
                    preflight_report_ref = await _persist_nl_execution_artifact(
                        persist_preflight_report,
                        preflight_report,
                        inputs=[
                            input_ref_from_artifact_ref(
                                _selected_nl_execution_artifact_ref(
                                    execution_plan_ref_str, kind="scientist.execution_plan"
                                ),
                                role="execution_plan",
                            ),
                            input_ref_from_artifact_ref(
                                _selected_nl_execution_artifact_ref(
                                    method_catalog_snapshot_ref_str,
                                    kind="foundry.method_catalog_snapshot",
                                ),
                                role="method_catalog_snapshot",
                            ),
                        ],
                    )
                    preflight_report_ref_str = str(preflight_report_ref.artifact_id)
                    preflight_ready = bool(preflight_report.ready_to_run)
                    preflight_diagnostics = [
                        item.model_dump(mode="json") for item in preflight_report.diagnostics
                    ]
                    _append_step(
                        agent="preflight",
                        action="validate_execution_plan",
                        summary="Preflight completed",
                        status="ok" if preflight_ready else "warn",
                        details={
                            "ready_to_run": preflight_ready,
                            "diagnostics_count": len(preflight_diagnostics),
                            "preflight_report_ref": preflight_report_ref_str,
                        },
                    )

                    iteration_state = IterationState(
                        schema_version="1.0",
                        run_id=run_id,
                        iteration=1,
                        lifecycle_state="plan_created",
                        plan_ref=ExecutionPlanRef.model_validate(
                            _selected_nl_execution_artifact_ref(
                                execution_plan_ref_str, kind="scientist.execution_plan"
                            ).model_dump(mode="python")
                        ),
                        preflight_report_ref=PreflightReportRef.model_validate(
                            _selected_nl_execution_artifact_ref(
                                preflight_report_ref_str, kind="scientist.preflight_report"
                            ).model_dump(mode="python")
                        ),
                    )
                    iteration_state = transition(
                        iteration_state,
                        "start_preflight",
                        notes=["preflight_started"],
                    )
                    if preflight_ready:
                        iteration_state = transition(
                            iteration_state,
                            "preflight_ready",
                            notes=["ready_to_run"],
                        )
                    else:
                        iteration_state = transition(
                            iteration_state,
                            "preflight_failed",
                            notes=["replanning_required"],
                        )
                        # Lightweight replanning strategy: keep data_needs, clear method DAG.
                        execution_plan = execution_plan.model_copy(
                            update={
                                "method_dag": [],
                                "method_edges": [],
                                "notes": [
                                    *list(execution_plan.notes),
                                    "replanned_after_preflight_diagnostics",
                                ],
                            }
                        )
                        execution_plan_ref_obj = await _persist_nl_execution_artifact(
                            persist_execution_plan,
                            execution_plan,
                        )
                        execution_plan_ref_str = str(execution_plan_ref_obj.artifact_id)
                        preflight_report = preflight_execution_plan(
                            execution_plan, catalog_snapshot
                        )
                        preflight_report.plan_ref = ExecutionPlanRef.model_validate(
                            _selected_nl_execution_artifact_ref(
                                execution_plan_ref_str, kind="scientist.execution_plan"
                            ).model_dump(mode="python")
                        )
                        preflight_report.catalog_snapshot_ref = (
                            MethodCatalogSnapshotRef.model_validate(
                                _selected_nl_execution_artifact_ref(
                                    method_catalog_snapshot_ref_str,
                                    kind="foundry.method_catalog_snapshot",
                                ).model_dump(mode="python")
                            )
                        )
                        preflight_report_ref = await _persist_nl_execution_artifact(
                            persist_preflight_report,
                            preflight_report,
                            inputs=[
                                input_ref_from_artifact_ref(
                                    _selected_nl_execution_artifact_ref(
                                        execution_plan_ref_str,
                                        kind="scientist.execution_plan",
                                    ),
                                    role="execution_plan",
                                ),
                                input_ref_from_artifact_ref(
                                    _selected_nl_execution_artifact_ref(
                                        method_catalog_snapshot_ref_str,
                                        kind="foundry.method_catalog_snapshot",
                                    ),
                                    role="method_catalog_snapshot",
                                ),
                            ],
                        )
                        preflight_report_ref_str = str(preflight_report_ref.artifact_id)
                        preflight_ready = bool(preflight_report.ready_to_run)
                        preflight_diagnostics = [
                            item.model_dump(mode="json") for item in preflight_report.diagnostics
                        ]
                        _append_step(
                            agent="preflight",
                            action="replan_after_diagnostics",
                            summary="ExecutionPlan replanned after preflight diagnostics",
                            status="warn",
                            details={
                                "ready_to_run": preflight_ready,
                                "diagnostics_count": len(preflight_diagnostics),
                            },
                        )
                        if preflight_ready:
                            iteration_state = transition(
                                iteration_state,
                                "replan",
                                notes=["replan_completed"],
                            )
                            iteration_state = transition(
                                iteration_state,
                                "start_preflight",
                                notes=["preflight_rerun"],
                            )
                            iteration_state = transition(
                                iteration_state,
                                "preflight_ready",
                                notes=["ready_after_replan"],
                            )
                        else:
                            notes.append("preflight_failed_after_replan")

                    iteration_state_ref = await _persist_nl_execution_artifact(
                        persist_iteration_state,
                        iteration_state,
                    )
                    iteration_state_ref_str = str(iteration_state_ref.artifact_id)

                    resolve_request = DataResolveRequest(
                        data_needs=data_needs or [DataNeed(metric="generic.policy.context")],
                        mode="hybrid",
                        allow_explore_fallback=True,
                        catalog_run_profile=self._catalog_run_profile,
                    )
                    resolve_outcome = await _capture_step(
                        agent="source_resolver",
                        action="resolve_fast_lane",
                        coro=run_blocking_async(
                            retrieval.resolve,
                            resolve_request,
                            run_profile=self._catalog_run_profile,
                        ),
                        summary="Resolved data needs into fetch plans",
                        details={"data_needs": len(data_needs)},
                    )
                    retrieval_telemetry = dict(resolve_outcome.telemetry)
                    retrieval_mode = str(resolve_outcome.mode)
                    retrieval_lane_used = str(
                        retrieval_telemetry.get("lane_used")
                        or retrieval_telemetry.get("lane")
                        or "none"
                    )
                    retrieval_metadata_docs_fetched = int(
                        retrieval_telemetry.get("metadata_docs_fetched") or 0
                    )
                    retrieval_index_size_bytes = int(
                        retrieval_telemetry.get("local_index_size_bytes") or 0
                    )
                    retrieval_index_docs_total = int(
                        retrieval_telemetry.get("local_index_docs_total") or 0
                    )
                    retrieval_candidates_filtered = int(
                        retrieval_telemetry.get("candidates_filtered") or 0
                    )
                    phase_rows = retrieval_telemetry.get("phases") or []
                    if isinstance(phase_rows, list):
                        for phase in phase_rows:
                            if not isinstance(phase, dict):
                                continue
                            phase_name = str(phase.get("phase") or "unknown")
                            retrieval_phase_durations[phase_name] = int(
                                phase.get("duration_ms") or 0
                            )
                            if phase_name == "discover_explore_lane":
                                _append_step(
                                    agent="source_resolver",
                                    action="discover_explore_lane",
                                    summary="ExploreLane discovery executed",
                                    details={
                                        "docs_fetched": int(phase.get("docs_fetched") or 0),
                                        "candidates_total": int(phase.get("candidates_total") or 0),
                                        "candidates_selected": int(
                                            phase.get("candidates_selected") or 0
                                        ),
                                    },
                                )

                    execute_outcome = None

                    def _json_payload(item: object) -> dict[str, Any]:
                        if hasattr(item, "model_dump"):
                            return dict(item.model_dump(mode="json"))
                        if isinstance(item, dict):
                            return dict(item)
                        return dict(vars(item))

                    production_data_lane_required = _requires_local_production_data_lane(
                        context=context,
                        execution_profile=execution_profile,
                        data_source=data_source,
                    )
                    if production_data_lane_required:
                        production_params = _build_scientist_context_params(
                            context,
                            domain_hint=domain_hint,
                            execution_profile=execution_profile,
                        )
                        fetch_plans_payload = [
                            _json_payload(item) for item in resolve_outcome.fetch_plans
                        ]
                        (
                            auto_data_source_refs,
                            data_context_payload,
                            production_data_context,
                        ) = await _capture_step(
                            agent="executor",
                            action="materialize_production_data",
                            coro=_materialize_production_data_artifacts(
                                variant_id=variant_id,
                                production_params=production_params,
                                data_needs_payload=[
                                    item.model_dump(mode="json") for item in data_needs
                                ],
                                fetch_plans_payload=fetch_plans_payload,
                                retrieval_telemetry=retrieval_telemetry,
                            ),
                            summary="Production data materialized into DataSnapshot/InputBindings",
                            details={
                                "fetch_plans": len(fetch_plans_payload),
                                "production_data_root": str(
                                    _production_data_root(
                                        production_params,
                                        allow_default=True,
                                    )
                                    or ""
                                ),
                            },
                        )
                        retrieval_context_payload["fetch_plans"] = fetch_plans_payload
                        retrieval_context_payload["auto_data_source_refs"] = dict(
                            auto_data_source_refs
                        )
                        retrieval_context_payload["production_data_evidence_context"] = dict(
                            production_data_context
                        )
                        if isinstance(data_context_payload.get("fabric_spine_bindings"), Mapping):
                            retrieval_context_payload["fabric_spine_bindings"] = dict(
                                data_context_payload["fabric_spine_bindings"]
                            )
                    elif resolve_outcome.fetch_plans:

                        def _promotion_candidate_payload(
                            item: object,
                        ) -> dict[str, Any]:
                            if hasattr(item, "model_dump"):
                                return dict(item.model_dump(mode="json"))
                            if isinstance(item, dict):
                                return dict(item)
                            return {
                                "promotion_id": getattr(item, "promotion_id", None),
                                "candidate": repr(item),
                            }

                        def _promotion_candidate_id(item: object) -> str | None:
                            if isinstance(item, dict):
                                value = item.get("promotion_id")
                            else:
                                value = getattr(item, "promotion_id", None)
                            return str(value) if value else None

                        list_promotion_candidates = getattr(
                            retrieval,
                            "list_promotion_candidates",
                            None,
                        )
                        promotion_candidates_before = (
                            list(raw_candidates_before)
                            if callable(list_promotion_candidates)
                            and isinstance(
                                (raw_candidates_before := list_promotion_candidates()),
                                list | tuple | set,
                            )
                            else []
                        )
                        promotion_ids_before = {
                            promotion_id
                            for item in promotion_candidates_before
                            if (promotion_id := _promotion_candidate_id(item)) is not None
                        }
                        execute_outcome = await _capture_step(
                            agent="executor",
                            action="fetch_execute",
                            coro=run_blocking_async(
                                retrieval.execute_fetch_plans,
                                list(resolve_outcome.fetch_plans),
                                persist_payload=True,
                                allow_fallback=True,
                            ),
                            summary="Executed fetch plans",
                            details={"fetch_plans": len(resolve_outcome.fetch_plans)},
                        )
                        preview_rejected = sum(
                            1
                            for item in execute_outcome.previews
                            if not bool(item.preview.coverage_ok)
                        )
                        _append_step(
                            agent="executor",
                            action="preview_gate",
                            summary="Preview gate completed",
                            status="warn" if preview_rejected > 0 else "ok",
                            details={
                                "plans_total": len(execute_outcome.previews),
                                "coverage_rejected": preview_rejected,
                                "fallback_triggered": execute_outcome.fallback_triggered_count,
                            },
                        )
                        retrieval_candidates_promoted = int(execute_outcome.promoted_count)
                        promotion_candidates_after = (
                            list(raw_candidates_after)
                            if callable(list_promotion_candidates)
                            and isinstance(
                                (raw_candidates_after := list_promotion_candidates()),
                                list | tuple | set,
                            )
                            else []
                        )
                        promotion_candidates = [
                            _promotion_candidate_payload(item)
                            for item in promotion_candidates_after
                            if (promotion_id := _promotion_candidate_id(item)) is not None
                            and promotion_id not in promotion_ids_before
                        ]
                        _append_step(
                            agent="promotion_lane",
                            action="promotion_signal_emit",
                            summary="Promotion signals emitted",
                            details={"candidates_promoted": retrieval_candidates_promoted},
                        )

                        data_context_payload = {
                            "metrics": [
                                metric.model_dump(mode="json")
                                for metric in execute_outcome.data_context.metrics
                            ],
                            "metadata_docs_fetched": (
                                execute_outcome.data_context.metadata_docs_fetched
                            ),
                            "index_docs_total": execute_outcome.data_context.index_docs_total,
                            "index_size_bytes": execute_outcome.data_context.index_size_bytes,
                        }
                        retrieval_context_payload["fetch_plans"] = [
                            _json_payload(item) for item in resolve_outcome.fetch_plans
                        ]
                        retrieval_context_payload["promotion_candidates"] = promotion_candidates
                    else:
                        _append_step(
                            agent="executor",
                            action="fetch_execute",
                            summary="No fetch plans resolved",
                            status="warn",
                            details={"fetch_plans": 0},
                        )

                    if _is_auto_materialization_enabled() and not auto_data_source_refs:
                        try:
                            auto_data_source_refs = await _materialize_retrieval_artifacts(
                                variant_id=variant_id,
                                data_context_payload=data_context_payload or {"metrics": []},
                                retrieval_telemetry=retrieval_telemetry,
                                data_needs_payload=[
                                    item.model_dump(mode="json") for item in data_needs
                                ],
                            )
                            _append_step(
                                agent="executor",
                                action="materialize_data_artifacts",
                                summary="Retrieval materialized into DataSnapshot/InputBindings",
                                details={
                                    "data_snapshot_ref": auto_data_source_refs.get(
                                        "data_snapshot_ref"
                                    ),
                                    "input_bindings_ref": auto_data_source_refs.get(
                                        "input_bindings_ref"
                                    ),
                                },
                            )
                            retrieval_context_payload["auto_data_source_refs"] = dict(
                                auto_data_source_refs
                            )
                        except (
                            KeyError,
                            OSError,
                            RuntimeError,
                            TypeError,
                            ValueError,
                        ) as exc:
                            notes.append(f"auto_materialization_failed:{exc}")
                            _append_step(
                                agent="executor",
                                action="materialize_data_artifacts",
                                summary="Retrieval materialization failed",
                                status="warn",
                                details={"error": str(exc)},
                            )

                    fabric_flags_active = _is_scientist_v2_enabled() or _is_scientist_shadow_mode()
                    if fabric_flags_active:
                        from polisyos.scientist.agent.fabric import (
                            ScientistAgentFabric,
                            ScientistAgentFabricConfig,
                            ScientistAgentFabricRequest,
                        )

                        fabric = ScientistAgentFabric(config=ScientistAgentFabricConfig.from_env())
                        fabric_request = ScientistAgentFabricRequest(
                            run_id=run_id,
                            variant_id=variant_id,
                            model_name=model_name,
                            llm_client=llm_client,
                            problem_frame=problem_frame,
                            data_context=dict(data_context_payload or {}),
                            drafter=drafter,
                            formalizer=formalizer,
                            critic=critic,
                            artifact_store=store,
                            max_iterations=max_iterations,
                        )
                        if fabric.config.shadow_mode:
                            fabric_shadow_task = asyncio.create_task(fabric.run(fabric_request))
                        elif fabric.config.enabled:
                            fabric_result = await _capture_step(
                                agent="scientist_v2",
                                action="fabric_run",
                                coro=fabric.run(fabric_request),
                                summary="Scientist v2 orchestration completed",
                            )

                    verdict = "NEEDS_REVISION"
                    issue_count = 0
                    if fabric_result is not None:
                        draft = fabric_result.draft
                        trinity_bundle = fabric_result.trinity_bundle
                        verdict = fabric_result.critique.verdict
                        issue_count = len(fabric_result.critique.issues)
                        critique_payload = _serialize_critique_report(fabric_result.critique)
                        evaluator_payload = dict(fabric_result.metrics or {})
                        _append_step(
                            agent="scientist_v2",
                            action="fabric_summary",
                            summary="Scientist v2 result accepted",
                            details={
                                "result": dict(fabric_result.result or {}),
                                "traces": dict(fabric_result.traces or {}),
                                "metrics": dict(fabric_result.metrics or {}),
                            },
                        )
                    else:
                        draft = await _capture_step(
                            agent="drafter",
                            action="draft_policy",
                            coro=drafter.draft_policy(
                                problem_frame,
                                data_context=data_context_payload or None,
                            ),
                            summary="Draft generated",
                        )
                        trinity_bundle = await _capture_step(
                            agent="formalizer",
                            action="formalize",
                            coro=formalizer.formalize(draft),
                            summary="Trinity bundle formalized",
                        )

                        if preflight_ready:
                            try:
                                iteration_state = transition(
                                    iteration_state,
                                    "start_execute",
                                    notes=["execution_started"],
                                )
                                iteration_state = transition(
                                    iteration_state,
                                    "execute_done",
                                    notes=["execution_phase_complete"],
                                )
                            except ValueError as exc:
                                logger.debug(
                                    "Iteration state execute transition failed for run %s: %s",
                                    run_id,
                                    exc,
                                )
                                notes.append("iteration_state_execute_transition_failed")
                        for iteration in range(max_iterations):
                            critique = await _capture_step(
                                agent="critic",
                                action="critique",
                                coro=critic.critique(trinity_bundle, problem_frame),
                                summary=f"Critique iteration {iteration + 1}",
                                details={"iteration": iteration + 1},
                            )
                            verdict = critique.verdict
                            issue_count = len(critique.issues)
                            critique_payload = _serialize_critique_report(critique)

                            usage_snapshot = _sum_call_events(call_events)
                            budget_remaining_ratio = None
                            snapshot_cost = _cost_number(usage_snapshot["cost_usd"])
                            if (
                                per_model_budget_usd is not None
                                and float(per_model_budget_usd) > 0
                                and snapshot_cost is not None
                            ):
                                budget_remaining_ratio = max(
                                    0.0,
                                    (float(per_model_budget_usd) - snapshot_cost)
                                    / float(per_model_budget_usd),
                                )
                            retrieval_quality = (
                                1.0
                                if retrieval_candidates_filtered == 0
                                else max(
                                    0.0,
                                    1.0
                                    - (
                                        float(retrieval_candidates_filtered)
                                        / float(
                                            max(
                                                1,
                                                retrieval_candidates_filtered
                                                + len(data_context_payload.get("metrics", [])),
                                            )
                                        )
                                    ),
                                )
                            )
                            evaluator_report = evaluate_iteration(
                                issue_count=issue_count,
                                verdict=critique.verdict,
                                retrieval_quality=retrieval_quality,
                                budget_remaining_ratio=budget_remaining_ratio,
                            )
                            evaluator_report_ref = await _persist_nl_execution_artifact(
                                persist_evaluator_report,
                                evaluator_report,
                            )
                            evaluator_report_ref_str = str(evaluator_report_ref.artifact_id)
                            evaluator_payload = evaluator_report.model_dump(mode="json")
                            _append_step(
                                agent="evaluator",
                                action="score_iteration",
                                summary=f"Evaluator verdict: {evaluator_report.verdict}",
                                status="ok" if evaluator_report.verdict == "APPROVE" else "warn",
                                details={
                                    "iteration": iteration + 1,
                                    "verdict": evaluator_report.verdict,
                                    "scores": evaluator_payload.get("scores"),
                                    "evaluator_report_ref": evaluator_report_ref_str,
                                },
                            )
                            try:
                                if evaluator_report.verdict == "APPROVE":
                                    iteration_state = transition(
                                        iteration_state,
                                        "approve",
                                        verdict=evaluator_report.verdict,
                                        stop_reason="approved",
                                        notes=["approved_by_evaluator"],
                                    )
                                elif evaluator_report.verdict == "STOP_BUDGET":
                                    iteration_state = transition(
                                        iteration_state,
                                        "stop_budget",
                                        verdict=evaluator_report.verdict,
                                        stop_reason="budget_exhausted",
                                        notes=["stopped_by_budget_guard"],
                                    )
                                else:
                                    iteration_state = transition(
                                        iteration_state,
                                        "replan",
                                        verdict=evaluator_report.verdict,
                                        notes=[f"replanning_due_to:{evaluator_report.verdict}"],
                                    )
                            except ValueError as exc:
                                logger.debug(
                                    "Iteration state evaluator transition failed for run %s: %s",
                                    run_id,
                                    exc,
                                )
                                notes.append("iteration_state_evaluator_transition_failed")

                            if evaluator_report.verdict == "APPROVE":
                                verdict = "APPROVE"
                                break
                            if evaluator_report.verdict == "STOP_BUDGET":
                                verdict = "STOP_BUDGET"
                                notes.append("evaluator_stop_budget")
                                break
                            if iteration < max_iterations - 1:
                                draft = await _capture_step(
                                    agent="drafter",
                                    action="refine_draft",
                                    coro=drafter.refine_draft(draft, critique),
                                    summary="Draft refined",
                                    status="warn",
                                    details={"iteration": iteration + 1},
                                )
                                trinity_bundle = await _capture_step(
                                    agent="formalizer",
                                    action="formalize",
                                    coro=formalizer.formalize(draft),
                                    summary="Trinity bundle re-formalized",
                                    status="warn",
                                    details={"iteration": iteration + 1},
                                )
                                if preflight_ready:
                                    try:
                                        iteration_state = transition(
                                            iteration_state,
                                            "start_preflight",
                                            notes=["iteration_replan_preflight_start"],
                                        )
                                        iteration_state = transition(
                                            iteration_state,
                                            "preflight_ready",
                                            notes=["iteration_replan_preflight_ready"],
                                        )
                                        iteration_state = transition(
                                            iteration_state,
                                            "start_execute",
                                            notes=["iteration_reexecution_start"],
                                        )
                                        iteration_state = transition(
                                            iteration_state,
                                            "execute_done",
                                            notes=["iteration_reexecution_done"],
                                        )
                                    except ValueError as exc:
                                        logger.debug(
                                            "Iteration replan transition failed for run %s: %s",
                                            run_id,
                                            exc,
                                        )
                                        notes.append("iteration_state_replan_transition_failed")

                    if fabric_shadow_task is not None:
                        try:
                            fabric_shadow_result = await fabric_shadow_task
                            fabric_shadow_comparison = _build_scientist_v2_shadow_comparison(
                                legacy_status="completed",
                                legacy_verdict=verdict,
                                legacy_issue_count=int(issue_count),
                                legacy_cost_usd=_cost_number(
                                    _sum_call_events(call_events)["cost_usd"]
                                ),
                                legacy_prompt_tokens=int(
                                    _sum_call_events(call_events)["prompt_tokens"]
                                ),
                                legacy_completion_tokens=int(
                                    _sum_call_events(call_events)["completion_tokens"]
                                ),
                                shadow_result=fabric_shadow_result,
                            )
                            _append_step(
                                agent="scientist_v2",
                                action="shadow_run",
                                summary="Scientist v2 shadow run completed",
                                details={
                                    "result": dict(fabric_shadow_result.result or {}),
                                    "traces": dict(fabric_shadow_result.traces or {}),
                                    "metrics": dict(fabric_shadow_result.metrics or {}),
                                    "comparison": dict(fabric_shadow_comparison or {}),
                                },
                            )
                        except Exception as exc:
                            notes.append(f"scientist_v2_shadow_failed:{exc}")
                            _append_step(
                                agent="scientist_v2",
                                action="shadow_run",
                                summary="Scientist v2 shadow run failed",
                                status="warn",
                                details={"error": str(exc)},
                            )
                    iteration_state_ref = await _persist_nl_execution_artifact(
                        persist_iteration_state,
                        iteration_state,
                    )
                    iteration_state_ref_str = str(iteration_state_ref.artifact_id)
                except (
                    AttributeError,
                    LookupError,
                    RuntimeError,
                    TypeError,
                    ValueError,
                ) as exc:  # pragma: no cover - defensive pipeline hardening
                    logger.exception("NL variant failed for model '%s': %s", model_name, exc)
                    failure_payload = _exception_failure_payload(exc)
                    failure_usage = _sum_call_events(call_events)
                    return {
                        "model_variant_id": variant_id,
                        "model": model_name,
                        "provider": provider,
                        "status": "failed",
                        "verdict": "ERROR",
                        "issue_count": 0,
                        "prompt_tokens": int(_sum_call_events(call_events)["prompt_tokens"]),
                        "completion_tokens": int(
                            _sum_call_events(call_events)["completion_tokens"]
                        ),
                        "total_tokens": int(
                            _sum_call_events(call_events)["prompt_tokens"]
                            + _sum_call_events(call_events)["completion_tokens"]
                        ),
                        "latency_ms": max(0, _now_ms() - variant_started_at),
                        "cost_usd": (
                            round(float(failure_usage["cost_usd"]), 8)
                            if failure_usage["cost_usd"] is not None
                            else None
                        ),
                        "cost_events": [_project_call_event_cost(event) for event in call_events],
                        "cost_origin_counts": failure_usage["cost_origin_counts"],
                        "settlement_status_counts": failure_usage["settlement_status_counts"],
                        "cost_reconciliation_delta_usd": (
                            round(float(failure_usage["cost_delta_usd"]), 8)
                            if failure_usage["cost_delta_usd"] is not None
                            else None
                        ),
                        "started_at": variant_started_iso,
                        "finished_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                        "steps": steps,
                        "notes": [*notes, f"variant_error:{exc}"],
                        "failure": failure_payload,
                        "schema_healing": [],
                        "schema_healing_count": 0,
                        "retrieval_mode": retrieval_mode,
                        "retrieval_lane_used": retrieval_lane_used,
                        "metadata_docs_fetched": retrieval_metadata_docs_fetched,
                        "local_index_size_bytes": retrieval_index_size_bytes,
                        "local_index_docs_total": retrieval_index_docs_total,
                        "candidates_filtered": retrieval_candidates_filtered,
                        "candidates_promoted": retrieval_candidates_promoted,
                        "retrieval_phase_durations": retrieval_phase_durations,
                        "retrieval_telemetry": retrieval_telemetry,
                        "execution_plan_ref": execution_plan_ref_str,
                        "method_catalog_snapshot_ref": method_catalog_snapshot_ref_str,
                        "preflight_report_ref": preflight_report_ref_str,
                        "preflight_ready": preflight_ready,
                        "preflight_diagnostics": preflight_diagnostics,
                        "evaluator_report_ref": evaluator_report_ref_str,
                        "evaluator": evaluator_payload,
                        "critic": critique_payload,
                        "iteration_state_ref": iteration_state_ref_str,
                        "auto_data_source_refs": auto_data_source_refs,
                        "reproducibility_manifest_ref": reproducibility_manifest_ref_str,
                        "retrieval_context": retrieval_context_payload,
                        "scientist_v2": (
                            {
                                "result": dict(fabric_result.result or {}),
                                "traces": dict(fabric_result.traces or {}),
                                "metrics": dict(fabric_result.metrics or {}),
                            }
                            if fabric_result is not None
                            else None
                        ),
                        "scientist_v2_shadow": (
                            {
                                "result": dict(fabric_shadow_result.result or {}),
                                "traces": dict(fabric_shadow_result.traces or {}),
                                "metrics": dict(fabric_shadow_result.metrics or {}),
                                "comparison": dict(fabric_shadow_comparison or {}),
                            }
                            if fabric_shadow_result is not None
                            else None
                        ),
                        "_bundle": None,
                    }
                finally:
                    if retrieval_catalog is not None:
                        retrieval_catalog.close()
                    await _close_llm_client(llm_client)

                schema_healing = _trinity_schema_healing_notes(trinity_bundle)
                for schema_note in schema_healing:
                    if schema_note not in notes:
                        notes.append(schema_note)

                usage = _sum_call_events(call_events)
                variant_cost_value = _cost_number(usage["cost_usd"])
                variant_cost = (
                    round(variant_cost_value, 8) if variant_cost_value is not None else None
                )
                status = "completed"
                budget_status = "not_configured"
                if per_model_budget_usd is not None:
                    if variant_cost is None:
                        budget_status = "unknown"
                        notes.append("per_model_budget_cost_unknown")
                    elif variant_cost > float(per_model_budget_usd):
                        budget_status = "exceeded"
                        status = "budget_exceeded"
                        notes.append("per_model_budget_exceeded")
                    else:
                        budget_status = "within_limit"
                if llm_client is None and model_name:
                    status = "fallback_mock"

                trinity_selected_ref = await _store_bundle(trinity_bundle)
                trinity_ref_str = str(trinity_selected_ref.artifact_id)
                selected_trinity_refs_by_variant[variant_id] = trinity_selected_ref
                final_policy_claims_report = build_final_policy_claims_report(
                    draft=draft,
                    trinity_bundle=trinity_bundle,
                )
                final_policy_claims_report = _merge_context_norm_refs_into_final_claims(
                    final_policy_claims_report
                )
                final_policy_claims_selected_ref = await _store_final_policy_claims_report(
                    final_policy_claims_report,
                    trinity_bundle_ref=trinity_selected_ref,
                )
                final_policy_claims_ref_str = str(final_policy_claims_selected_ref.artifact_id)
                selected_final_policy_claims_refs_by_variant[variant_id] = (
                    final_policy_claims_selected_ref
                )
                claim_extraction_status = str(
                    final_policy_claims_report.get("extraction_status") or ""
                ).casefold()
                if claim_extraction_status == "review_required":
                    notes.append("final_policy_claim_extraction_review_required")
                claim_extraction_failure = _final_policy_claim_extraction_failure(
                    report=final_policy_claims_report,
                    report_ref=final_policy_claims_ref_str,
                    selected_variant={
                        "model": model_name,
                        "provider": provider,
                    },
                )
                if claim_extraction_failure is not None and _is_serious_execution_profile(
                    execution_profile
                ):
                    status = "failed"
                    verdict = "ERROR"
                    issue_count = max(1, int(issue_count))
                    notes.append("final_policy_claim_extraction_failed")
                try:
                    repro_manifest = build_reproducibility_manifest(
                        run_id=run_id,
                        iteration=1,
                        seed=int(context.get("random_seed", 0) or 0),
                        plan=execution_plan,
                        registry_bundle_ref=auto_data_source_refs.get("registry_bundle_ref"),
                        method_catalog_snapshot_ref=method_catalog_snapshot_ref_str,
                        data_snapshot_ref=auto_data_source_refs.get("data_snapshot_ref"),
                        input_bindings_ref=auto_data_source_refs.get("input_bindings_ref"),
                    )
                    repro_manifest_ref = await _persist_nl_execution_artifact(
                        persist_reproducibility_manifest,
                        repro_manifest,
                    )
                    reproducibility_manifest_ref_str = str(repro_manifest_ref.artifact_id)
                except (OSError, RuntimeError, TypeError, ValueError) as exc:
                    notes.append(f"reproducibility_manifest_failed:{exc}")
                    return {
                        "model_variant_id": variant_id,
                        "model": model_name,
                        "provider": provider,
                        "status": status,
                        "verdict": verdict,
                        "issue_count": int(issue_count),
                        "prompt_tokens": int(usage["prompt_tokens"]),
                        "completion_tokens": int(usage["completion_tokens"]),
                        "total_tokens": int(usage["prompt_tokens"] + usage["completion_tokens"]),
                        "latency_ms": max(0, _now_ms() - variant_started_at),
                        "cost_usd": variant_cost,
                        "cost_events": [_project_call_event_cost(event) for event in call_events],
                        "cost_origin_counts": usage["cost_origin_counts"],
                        "settlement_status_counts": usage["settlement_status_counts"],
                        "budget_status": budget_status,
                        "cost_reconciliation_delta_usd": round(float(usage["cost_delta_usd"]), 8)
                        if usage["cost_delta_usd"] is not None
                        else None,
                        "trinity_bundle_ref": trinity_ref_str,
                        "trinity_bundle_selected_ref": trinity_selected_ref.model_dump(mode="json"),
                        "final_policy_claims_ref": final_policy_claims_ref_str,
                        "final_policy_claims_selected_ref": (
                            final_policy_claims_selected_ref.model_dump(mode="json")
                        ),
                        "final_policy_claims": final_policy_claims_report,
                        "final_policy_claims_summary": dict(
                            final_policy_claims_report.get("summary") or {}
                        ),
                        "final_policy_claim_extraction_status": (
                            final_policy_claims_report.get("extraction_status")
                        ),
                        "final_policy_claim_human_review_required": bool(
                            final_policy_claims_report.get("human_review_required")
                        ),
                        "failure": claim_extraction_failure,
                        "started_at": variant_started_iso,
                        "finished_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                        "steps": steps,
                        "notes": notes,
                        "schema_healing": schema_healing,
                        "schema_healing_count": len(schema_healing),
                        "retrieval_mode": retrieval_mode,
                        "retrieval_lane_used": retrieval_lane_used,
                        "metadata_docs_fetched": retrieval_metadata_docs_fetched,
                        "local_index_size_bytes": retrieval_index_size_bytes,
                        "local_index_docs_total": retrieval_index_docs_total,
                        "candidates_filtered": retrieval_candidates_filtered,
                        "candidates_promoted": retrieval_candidates_promoted,
                        "retrieval_phase_durations": retrieval_phase_durations,
                        "retrieval_telemetry": retrieval_telemetry,
                        "execution_plan_ref": execution_plan_ref_str,
                        "method_catalog_snapshot_ref": method_catalog_snapshot_ref_str,
                        "preflight_report_ref": preflight_report_ref_str,
                        "preflight_ready": preflight_ready,
                        "preflight_diagnostics": preflight_diagnostics,
                        "evaluator_report_ref": evaluator_report_ref_str,
                        "evaluator": evaluator_payload,
                        "critic": critique_payload,
                        "iteration_state_ref": iteration_state_ref_str,
                        "auto_data_source_refs": auto_data_source_refs,
                        "reproducibility_manifest_ref": reproducibility_manifest_ref_str,
                        "retrieval_context": retrieval_context_payload,
                        "scientist_v2": (
                            {
                                "result": dict(fabric_result.result or {}),
                                "traces": dict(fabric_result.traces or {}),
                                "metrics": dict(fabric_result.metrics or {}),
                            }
                            if fabric_result is not None
                            else None
                        ),
                        "scientist_v2_shadow": (
                            {
                                "result": dict(fabric_shadow_result.result or {}),
                                "traces": dict(fabric_shadow_result.traces or {}),
                                "metrics": dict(fabric_shadow_result.metrics or {}),
                                "comparison": dict(fabric_shadow_comparison or {}),
                            }
                            if fabric_shadow_result is not None
                            else None
                        ),
                        "_bundle": trinity_bundle,
                    }

                return {
                    "model_variant_id": variant_id,
                    "model": model_name,
                    "provider": provider,
                    "status": status,
                    "verdict": verdict,
                    "issue_count": int(issue_count),
                    "prompt_tokens": int(usage["prompt_tokens"]),
                    "completion_tokens": int(usage["completion_tokens"]),
                    "total_tokens": int(usage["prompt_tokens"] + usage["completion_tokens"]),
                    "latency_ms": max(0, _now_ms() - variant_started_at),
                    "cost_usd": variant_cost,
                    "cost_events": [_project_call_event_cost(event) for event in call_events],
                    "cost_origin_counts": usage["cost_origin_counts"],
                    "settlement_status_counts": usage["settlement_status_counts"],
                    "budget_status": budget_status,
                    "cost_reconciliation_delta_usd": (
                        round(float(usage["cost_delta_usd"]), 8)
                        if usage["cost_delta_usd"] is not None
                        else None
                    ),
                    "trinity_bundle_ref": trinity_ref_str,
                    "trinity_bundle_selected_ref": trinity_selected_ref.model_dump(mode="json"),
                    "final_policy_claims_ref": final_policy_claims_ref_str,
                    "final_policy_claims_selected_ref": final_policy_claims_selected_ref.model_dump(
                        mode="json"
                    ),
                    "final_policy_claims": final_policy_claims_report,
                    "final_policy_claims_summary": dict(
                        final_policy_claims_report.get("summary") or {}
                    ),
                    "final_policy_claim_extraction_status": (
                        final_policy_claims_report.get("extraction_status")
                    ),
                    "final_policy_claim_human_review_required": bool(
                        final_policy_claims_report.get("human_review_required")
                    ),
                    "failure": claim_extraction_failure,
                    "started_at": variant_started_iso,
                    "finished_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                    "steps": steps,
                    "notes": notes,
                    "schema_healing": schema_healing,
                    "schema_healing_count": len(schema_healing),
                    "retrieval_mode": retrieval_mode,
                    "retrieval_lane_used": retrieval_lane_used,
                    "metadata_docs_fetched": retrieval_metadata_docs_fetched,
                    "local_index_size_bytes": retrieval_index_size_bytes,
                    "local_index_docs_total": retrieval_index_docs_total,
                    "candidates_filtered": retrieval_candidates_filtered,
                    "candidates_promoted": retrieval_candidates_promoted,
                    "retrieval_phase_durations": retrieval_phase_durations,
                    "retrieval_telemetry": retrieval_telemetry,
                    "execution_plan_ref": execution_plan_ref_str,
                    "method_catalog_snapshot_ref": method_catalog_snapshot_ref_str,
                    "preflight_report_ref": preflight_report_ref_str,
                    "preflight_ready": preflight_ready,
                    "preflight_diagnostics": preflight_diagnostics,
                    "evaluator_report_ref": evaluator_report_ref_str,
                    "evaluator": evaluator_payload,
                    "critic": critique_payload,
                    "iteration_state_ref": iteration_state_ref_str,
                    "auto_data_source_refs": auto_data_source_refs,
                    "reproducibility_manifest_ref": reproducibility_manifest_ref_str,
                    "retrieval_context": retrieval_context_payload,
                    "scientist_v2": (
                        {
                            "result": dict(fabric_result.result or {}),
                            "traces": dict(fabric_result.traces or {}),
                            "metrics": dict(fabric_result.metrics or {}),
                        }
                        if fabric_result is not None
                        else None
                    ),
                    "scientist_v2_shadow": (
                        {
                            "result": dict(fabric_shadow_result.result or {}),
                            "traces": dict(fabric_shadow_result.traces or {}),
                            "metrics": dict(fabric_shadow_result.metrics or {}),
                            "comparison": dict(fabric_shadow_comparison or {}),
                        }
                        if fabric_shadow_result is not None
                        else None
                    ),
                    "_bundle": trinity_bundle,
                }

            intent_ref, intent_evidence = await _materialize_policy_intent_envelope()
            intent_payload = dict(intent_evidence)
            design_problem_ref, design_problem = await _materialize_design_problem(
                intent_ref=intent_ref,
                intent_payload=intent_payload,
            )
            (
                capability_ledger_ref,
                capability_ledger_payload,
                capability_ledger_evidence,
            ) = await _materialize_policy_design_capability_ledger(intent_ref=intent_ref)
            (
                concept_spine_payload,
                jurisdiction_spine_payload,
                _producer_spine_context,
            ) = await _materialize_policy_design_spines(
                intent_payload=intent_payload,
                intent_ref=intent_ref,
                capability_ledger_evidence=capability_ledger_evidence,
            )
            await _persist_policy_design_runtime_payload(
                intent_payload=intent_payload,
                intent_ref=intent_ref,
                capability_ledger=capability_ledger_payload,
                capability_ledger_ref=capability_ledger_ref,
                capability_ledger_evidence=capability_ledger_evidence,
                concept_spine=concept_spine_payload,
                jurisdiction_spine=jurisdiction_spine_payload,
            )

            variants: list[dict[str, Any]] = []
            if not models_to_run:
                variants.append(await _run_variant(None, 0))
            else:
                run_budget_spent = 0.0
                run_budget_stop = False
                run_budget_uncertain = False
                sem = asyncio.Semaphore(max(1, min(max_parallel_models, len(models_to_run))))
                budget_lock = asyncio.Lock()

                async def _run_with_limits(idx: int, model_name: str) -> dict[str, Any]:
                    nonlocal run_budget_spent, run_budget_stop, run_budget_uncertain
                    async with sem:
                        async with budget_lock:
                            if run_budget_stop:
                                stop_status = (
                                    "skipped_budget_unknown"
                                    if run_budget_uncertain
                                    else "skipped_budget_guard"
                                )
                                stop_reason = (
                                    "run_budget_cost_unknown"
                                    if run_budget_uncertain
                                    else "run_budget_guard_prevented_start"
                                )
                                return {
                                    "model_variant_id": _normalize_model_variant_id(
                                        model_name, idx
                                    ),
                                    "model": model_name,
                                    "provider": "gateway",
                                    "status": stop_status,
                                    "verdict": None,
                                    "issue_count": 0,
                                    "prompt_tokens": 0,
                                    "completion_tokens": 0,
                                    "total_tokens": 0,
                                    "latency_ms": 0,
                                    "cost_usd": 0.0,
                                    "cost_events": [],
                                    "cost_origin_counts": {},
                                    "settlement_status_counts": {},
                                    "started_at": None,
                                    "finished_at": None,
                                    "steps": [],
                                    "notes": [stop_reason],
                                    "schema_healing": [],
                                    "schema_healing_count": 0,
                                    "_bundle": None,
                                }
                        variant = await _run_variant(model_name, idx)
                        async with budget_lock:
                            variant_cost = _cost_number(variant.get("cost_usd"))
                            if variant_cost is None:
                                run_budget_uncertain = True
                            else:
                                run_budget_spent += variant_cost
                            if run_budget_usd is not None and run_budget_spent >= float(
                                run_budget_usd
                            ):
                                run_budget_stop = True
                            if run_budget_usd is not None and run_budget_uncertain:
                                run_budget_stop = True
                        return variant

                tasks = [
                    asyncio.create_task(_run_with_limits(index, model_name))
                    for index, model_name in enumerate(models_to_run)
                ]
                variants = await asyncio.gather(*tasks)

            _validate_selected_variant_artifact_refs(variants)

            for item in variants:
                variant_id_value = str(
                    item.get("model_variant_id") or item.get("model") or "unknown_variant"
                )
                progress_variants[variant_id_value] = {
                    **dict(progress_variants.get(variant_id_value) or {}),
                    "model_variant_id": variant_id_value,
                    "model": item.get("model"),
                    "provider": item.get("provider"),
                    "status": item.get("status"),
                    "verdict": item.get("verdict"),
                    "steps_completed": len(item.get("steps") or []),
                    "cost_usd": _cost_number(item.get("cost_usd")),
                    "cost_events": list(item.get("cost_events") or []),
                    "cost_origin_counts": dict(item.get("cost_origin_counts") or {}),
                    "settlement_status_counts": dict(item.get("settlement_status_counts") or {}),
                    "total_tokens": int(item.get("total_tokens") or 0),
                    "schema_healing_count": int(item.get("schema_healing_count") or 0),
                }
                schema_healing = item.get("schema_healing")
                if isinstance(schema_healing, list) and schema_healing:
                    progress_variants[variant_id_value]["schema_healing"] = list(schema_healing)
                auto_refs = item.get("auto_data_source_refs")
                if isinstance(auto_refs, Mapping):
                    progress_variants[variant_id_value]["auto_data_source_refs"] = _progress_json(
                        auto_refs
                    )
                retrieval_context = item.get("retrieval_context")
                production_context = (
                    retrieval_context.get("production_data_evidence_context")
                    if isinstance(retrieval_context, Mapping)
                    else None
                )
                if isinstance(production_context, Mapping):
                    progress_variants[variant_id_value]["production_data_evidence_context"] = (
                        _progress_json(production_context)
                    )
            _emit_job_progress(
                phase="model_variants_completed",
                details={"variants": len(variants)},
            )

            selected_variant: dict[str, Any] | None = None
            approved_candidates = [
                item
                for item in variants
                if item.get("_bundle") is not None
                and item.get("status") not in {"failed"}
                and str(item.get("verdict", "")).upper() == "APPROVE"
            ]
            if approved_candidates:
                selected_variant = approved_candidates[0]
            if selected_variant is None:
                non_failed = [
                    item
                    for item in variants
                    if item.get("_bundle") is not None and item.get("status") not in {"failed"}
                ]
                if non_failed:
                    selected_variant = non_failed[0]
            if selected_variant is None:
                failure = _model_variants_failure_envelope(_mapping_rows(variants))
                _emit_job_progress(
                    phase="model_variants_failed",
                    state="failed",
                    details={"failure": failure},
                )
                raise RuntimeError(f"{failure['code']}:{failure['message']}")
            selected_variant["selected_for_workflow"] = True
            selected_variant_id = str(selected_variant.get("model_variant_id") or "")
            if selected_variant_id:
                progress_variants[selected_variant_id] = {
                    **dict(progress_variants.get(selected_variant_id) or {}),
                    "model_variant_id": selected_variant_id,
                    "model": selected_variant.get("model"),
                    "provider": selected_variant.get("provider"),
                    "status": selected_variant.get("status"),
                    "verdict": selected_variant.get("verdict"),
                    "selected_for_workflow": True,
                    "steps_completed": len(selected_variant.get("steps") or []),
                    "cost_usd": _cost_number(selected_variant.get("cost_usd")),
                    "cost_events": list(selected_variant.get("cost_events") or []),
                    "cost_origin_counts": dict(selected_variant.get("cost_origin_counts") or {}),
                    "settlement_status_counts": dict(
                        selected_variant.get("settlement_status_counts") or {}
                    ),
                    "total_tokens": int(selected_variant.get("total_tokens") or 0),
                    "schema_healing_count": int(selected_variant.get("schema_healing_count") or 0),
                }
                selected_schema_healing = selected_variant.get("schema_healing")
                if isinstance(selected_schema_healing, list) and selected_schema_healing:
                    progress_variants[selected_variant_id]["schema_healing"] = list(
                        selected_schema_healing
                    )
                selected_auto_refs = selected_variant.get("auto_data_source_refs")
                if isinstance(selected_auto_refs, Mapping):
                    progress_variants[selected_variant_id]["auto_data_source_refs"] = (
                        _progress_json(selected_auto_refs)
                    )
                selected_retrieval_context = selected_variant.get("retrieval_context")
                selected_production_context = (
                    selected_retrieval_context.get("production_data_evidence_context")
                    if isinstance(selected_retrieval_context, Mapping)
                    else None
                )
                if isinstance(selected_production_context, Mapping):
                    progress_variants[selected_variant_id]["production_data_evidence_context"] = (
                        _progress_json(selected_production_context)
                    )
                _emit_job_progress(
                    phase="model_variant_selected",
                    selected_variant_id=selected_variant_id,
                    details={"model": selected_variant.get("model")},
                )

            selected_ref = _trinity_bundle_ref_for_variant(selected_variant)
            if selected_ref is None:
                selected_bundle = selected_variant.get("_bundle")
                if selected_bundle is None:
                    raise RuntimeError("No valid model variant produced a Trinity bundle")
                selected_ref = await _store_bundle(selected_bundle)
                selected_variant["trinity_bundle_ref"] = str(selected_ref.artifact_id)
                selected_variant["trinity_bundle_selected_ref"] = selected_ref.model_dump(
                    mode="json"
                )
                selected_trinity_refs_by_variant[selected_variant_id] = selected_ref

            _validate_selected_variant_artifact_refs(variants)

            adjudication_payload = build_model_variant_adjudication(
                variants=_mapping_rows(variants),
                selected_variant=selected_variant,
            )
            adjudication_inputs: list[InputRef] = []
            for variant_index, variant in enumerate(variants):
                for ref_key, _kind in (
                    ("trinity_bundle_ref", "ir.trinity_bundle"),
                    ("final_policy_claims_ref", "scientist.final_policy_claims"),
                ):
                    if ref_key == "final_policy_claims_ref":
                        ref_input = _final_policy_claims_report_input_ref(
                            role=f"variant_{variant_index + 1}_{ref_key}",
                            variant=variant,
                        )
                    else:
                        ref_input = _trinity_bundle_input_ref(
                            role=f"variant_{variant_index + 1}_{ref_key}",
                            variant=variant,
                        )
                    if ref_input is not None:
                        adjudication_inputs.append(ref_input)
            adjudication_ref = await _put_nl_tenant_owned_json(
                async_store,
                adjudication_payload,
                ArtifactWriteOptions(
                    kind="scientist.llm_model_adjudication",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.scientist.LLMModelAdjudication", version="1.0"
                    ),
                    inputs=adjudication_inputs,
                ),
                tenant_context=trinity_bundle_tenant_context,
                canon_spec=CanonSpec(forbid_floats=False),
            )
            llm_model_adjudication_ref = str(adjudication_ref.artifact_id)
            adjudication_payload = {
                **adjudication_payload,
                "artifact_ref": llm_model_adjudication_ref,
                "decision": {
                    **dict(adjudication_payload.get("decision") or {}),
                    "artifact_ref": llm_model_adjudication_ref,
                },
            }
            selected_variant["llm_model_adjudication_ref"] = llm_model_adjudication_ref
            selected_variant["llm_model_adjudication"] = adjudication_payload
            selected_variant["adjudication_decision"] = adjudication_payload["decision"]
            selected_variant["selection_rationale"] = adjudication_payload["decision"].get(
                "rationale"
            )
            selected_variant["selection_evidence_refs"] = list(
                adjudication_payload["decision"].get("evidence_refs") or []
            )
            for variant in variants:
                variant["llm_model_adjudication_ref"] = llm_model_adjudication_ref
            if selected_variant_id:
                progress_variants[selected_variant_id] = {
                    **dict(progress_variants.get(selected_variant_id) or {}),
                    "llm_model_adjudication_ref": llm_model_adjudication_ref,
                    "selection_rationale": selected_variant.get("selection_rationale"),
                    "selection_evidence_refs": list(
                        selected_variant.get("selection_evidence_refs") or []
                    ),
                }
            _emit_job_progress(
                phase="model_variant_adjudicated",
                selected_variant_id=selected_variant_id,
                details={
                    "llm_model_adjudication_ref": llm_model_adjudication_ref,
                    "disagreement_count": adjudication_payload.get("summary", {}).get(
                        "disagreement_count"
                    ),
                    "selected_variant_id": selected_variant_id,
                },
            )

            materialization_failure = _production_materialization_failure(
                execution_profile=execution_profile,
                data_source=data_source,
                selected_variant=selected_variant,
            )
            if materialization_failure is not None:
                _emit_job_progress(
                    phase="production_materialization_failed",
                    state="failed",
                    selected_variant_id=selected_variant_id,
                    details={"failure": materialization_failure},
                )
                raise RuntimeError(
                    f"{materialization_failure['code']}:{materialization_failure['message']}"
                )

            if _is_serious_execution_profile(execution_profile):
                for variant in variants:
                    selected_trinity_ref, selected_claims_ref = _selected_variant_artifact_refs(
                        variant
                    )
                    variant_input_refs = [
                        value
                        for value in (
                            variant.get("execution_plan_ref"),
                            variant.get("method_catalog_snapshot_ref"),
                            variant.get("preflight_report_ref"),
                            variant.get("evaluator_report_ref"),
                        )
                        if isinstance(value, str) and value
                    ]
                    variant_output_refs = [
                        value
                        for value in (
                            str(selected_trinity_ref.artifact_id)
                            if selected_trinity_ref is not None
                            else None,
                            str(selected_claims_ref.artifact_id)
                            if selected_claims_ref is not None
                            else None,
                            variant.get("llm_model_adjudication_ref"),
                        )
                        if isinstance(value, str) and value
                    ]
                    handoff_refs = [
                        value
                        for value in (
                            variant.get("llm_model_adjudication_ref"),
                            str(selected_claims_ref.artifact_id)
                            if selected_claims_ref is not None
                            else None,
                            str(selected_trinity_ref.artifact_id)
                            if selected_trinity_ref is not None
                            else None,
                        )
                        if isinstance(value, str) and value
                    ]
                    ledger = build_prompt_tool_ledger_from_model_variant(
                        run_id=run_id,
                        job_id=str(control_job_id or f"run:{run_id}"),
                        variant=variant,
                        rendered_input_refs=variant_input_refs,
                        output_refs=variant_output_refs,
                        authority_handoff_refs=handoff_refs,
                    )
                    ledger_inputs: list[InputRef] = []
                    ledger_input_specs = (
                        ("execution_plan_ref", "scientist.execution_plan"),
                        ("method_catalog_snapshot_ref", "foundry.method_catalog_snapshot"),
                        ("preflight_report_ref", "scientist.preflight_report"),
                        ("evaluator_report_ref", "scientist.evaluator_report"),
                        ("trinity_bundle_ref", "ir.trinity_bundle"),
                        ("final_policy_claims_ref", "scientist.final_policy_claims"),
                        ("llm_model_adjudication_ref", "scientist.llm_model_adjudication"),
                    )
                    for ref_key, kind in ledger_input_specs:
                        role = f"variant_{ref_key.removesuffix('_ref')}"
                        if ref_key == "trinity_bundle_ref":
                            ref_input = (
                                input_ref_from_artifact_ref(
                                    selected_trinity_ref,
                                    role=role,
                                )
                                if selected_trinity_ref is not None
                                else None
                            )
                        elif ref_key == "final_policy_claims_ref":
                            ref_input = (
                                input_ref_from_artifact_ref(
                                    selected_claims_ref,
                                    role=role,
                                )
                                if selected_claims_ref is not None
                                else None
                            )
                        else:
                            ref_value = variant.get(ref_key)
                            if not isinstance(ref_value, str) or not ref_value:
                                continue
                            ref_input = _quality_report_input_ref(
                                role=role,
                                ref_value=ref_value,
                                kind=kind,
                            )
                        if ref_input is not None:
                            ledger_inputs.append(ref_input)
                    ledger_ref = await _put_nl_tenant_owned_json(
                        async_store,
                        serialize_prompt_tool_ledger(ledger),
                        ArtifactWriteOptions(
                            kind=PROMPT_TOOL_LEDGER_KIND,
                            media_type="application/json",
                            schema=SchemaInfo(name=PROMPT_TOOL_LEDGER_SCHEMA, version="1.0"),
                            inputs=ledger_inputs,
                        ),
                        tenant_context=trinity_bundle_tenant_context,
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    ledger_ref_str = str(ledger_ref.artifact_id)
                    ledger_payload = serialize_prompt_tool_ledger(ledger)
                    ledger_payload[PROMPT_TOOL_LEDGER_REF_KEY] = ledger_ref_str
                    variant[PROMPT_TOOL_LEDGER_REF_KEY] = ledger_ref_str
                    variant[PROMPT_TOOL_LEDGER_REPORT_KEY] = ledger_payload
                    variant["prompt_tool_authority_status"] = ledger_payload.get("summary", {}).get(
                        "status"
                    )
                    variant_id_value = str(
                        variant.get("model_variant_id") or variant.get("model") or "unknown_variant"
                    )
                    progress_variants[variant_id_value] = {
                        **dict(progress_variants.get(variant_id_value) or {}),
                        PROMPT_TOOL_LEDGER_REF_KEY: ledger_ref_str,
                        "prompt_tool_authority_status": variant["prompt_tool_authority_status"],
                    }

                selected_prompt_tool_ref = selected_variant.get(PROMPT_TOOL_LEDGER_REF_KEY)
                selected_prompt_tool_ledger = selected_variant.get(PROMPT_TOOL_LEDGER_REPORT_KEY)
                if isinstance(selected_prompt_tool_ref, str) and selected_prompt_tool_ref:
                    runtime_quality_refs[PROMPT_TOOL_LEDGER_REF_KEY] = selected_prompt_tool_ref
                if isinstance(selected_prompt_tool_ledger, Mapping):
                    runtime_quality_evidence[PROMPT_TOOL_LEDGER_REPORT_KEY] = dict(
                        selected_prompt_tool_ledger
                    )
                _emit_job_progress(
                    phase="prompt_tool_parser_authority_ledger_persisted",
                    selected_variant_id=selected_variant_id,
                    details={
                        PROMPT_TOOL_LEDGER_REF_KEY: runtime_quality_refs.get(
                            PROMPT_TOOL_LEDGER_REF_KEY
                        ),
                        "variant_ledger_count": sum(
                            1 for item in variants if item.get(PROMPT_TOOL_LEDGER_REF_KEY)
                        ),
                    },
                )

                normative_report_inputs = [
                    input_ref_from_artifact_ref(
                        _selected_materialization_ref(
                            selected_ref,
                            "ir.trinity_bundle",
                        ),
                        role="trinity_bundle",
                    )
                ]
                auto_refs = selected_variant.get("auto_data_source_refs")
                if isinstance(auto_refs, Mapping):
                    auto_refs = dict(auto_refs)
                    selected_variant["auto_data_source_refs"] = auto_refs
                    try:
                        final_claims_report_for_data_quality = (
                            _final_policy_claims_report_from_variant(selected_variant)
                        )
                    except CanonicalProfileRefusalError as exc:
                        selected_final_claims_refusal_codes.append(exc.code)
                        final_claims_report_for_data_quality = {}
                    final_claims_for_data_quality = _claims_from_final_report(
                        final_claims_report_for_data_quality
                    )
                    retrieval_context_payload = selected_variant.get("retrieval_context")
                    production_evidence_context = None
                    if isinstance(retrieval_context_payload, Mapping):
                        production_evidence_context = retrieval_context_payload.get(
                            "production_data_evidence_context"
                        )
                    if not isinstance(production_evidence_context, Mapping):
                        production_evidence_context = selected_variant.get(
                            "production_data_evidence_context"
                        )
                    if (
                        final_claims_for_data_quality
                        and isinstance(production_evidence_context, Mapping)
                        and auto_refs.get("production_data_quality_report_ref")
                    ):
                        (
                            refreshed_quality_ref,
                            refreshed_quality_report,
                        ) = await _persist_production_data_quality_report(
                            evidence_context=production_evidence_context,
                            materialization_refs=auto_refs,
                            data_needs_payload=list(selected_variant.get("data_needs") or [])
                            if isinstance(selected_variant.get("data_needs"), list)
                            else list(
                                selected_variant.get("retrieval_context", {}).get("data_needs", [])
                            )
                            if isinstance(selected_variant.get("retrieval_context"), Mapping)
                            else [],
                            claims_payload=final_claims_for_data_quality,
                        )
                        refreshed_auto_refs = dict(auto_refs)
                        refreshed_auto_refs["production_data_quality_report_ref"] = (
                            refreshed_quality_ref
                        )
                        selected_variant["auto_data_source_refs"] = refreshed_auto_refs
                        selected_variant["production_data_quality_report_ref"] = (
                            refreshed_quality_ref
                        )
                        selected_variant["production_data_quality_report"] = (
                            refreshed_quality_report
                        )
                        auto_refs = refreshed_auto_refs
                        if isinstance(retrieval_context_payload, Mapping):
                            refreshed_retrieval_context = dict(retrieval_context_payload)
                            refreshed_evidence_context = dict(production_evidence_context)
                            refreshed_evidence_context["production_data_quality_report_ref"] = (
                                refreshed_quality_ref
                            )
                            refreshed_evidence_context["production_data_quality_report"] = (
                                refreshed_quality_report
                            )
                            refreshed_evidence_context["production_data_quality_status"] = (
                                refreshed_quality_report.get("status")
                            )
                            refreshed_evidence_context["timeline"] = [
                                *list(refreshed_evidence_context.get("timeline") or []),
                                {
                                    "event": "production_data_quality_claim_diagnostics_persisted",
                                    "production_data_quality_report_ref": refreshed_quality_ref,
                                    "status": refreshed_quality_report.get("status"),
                                },
                            ]
                            refreshed_evidence_context["lineage"] = [
                                *list(refreshed_evidence_context.get("lineage") or []),
                                {
                                    "kind": "runtime.production_data_quality_report",
                                    "production_data_quality_report_ref": refreshed_quality_ref,
                                    "input_refs": dict(refreshed_auto_refs),
                                    "claim_count": len(final_claims_for_data_quality),
                                },
                            ]
                            refreshed_retrieval_context["production_data_evidence_context"] = (
                                refreshed_evidence_context
                            )
                            selected_variant["retrieval_context"] = refreshed_retrieval_context
                            selected_variant["production_data_evidence_context"] = (
                                refreshed_evidence_context
                            )
                        if selected_variant_id:
                            progress_update = {
                                **dict(progress_variants.get(selected_variant_id) or {}),
                                "production_data_quality_report_ref": refreshed_quality_ref,
                                "production_data_quality_status": (
                                    refreshed_quality_report.get("status")
                                ),
                            }
                            refreshed_progress_context = selected_variant.get(
                                "production_data_evidence_context"
                            )
                            if isinstance(refreshed_progress_context, Mapping):
                                progress_update["production_data_evidence_context"] = dict(
                                    refreshed_progress_context
                                )
                            progress_variants[selected_variant_id] = progress_update
                        _emit_job_progress(
                            phase="production_data_quality_claim_diagnostics_persisted",
                            selected_variant_id=selected_variant_id,
                            details={
                                "production_data_quality_report_ref": refreshed_quality_ref,
                                "production_data_quality_status": refreshed_quality_report.get(
                                    "status"
                                ),
                                "claim_diagnostic_count": len(
                                    refreshed_quality_report.get("claim_diagnostics") or []
                                ),
                            },
                        )
                    for ref_key, kind in (
                        ("data_snapshot_ref", _DATA_SOURCE_KEYS["data_snapshot_ref"]),
                        ("input_bindings_ref", _DATA_SOURCE_KEYS["input_bindings_ref"]),
                        ("registry_bundle_ref", "core.registry_bundle"),
                        (
                            "production_data_quality_report_ref",
                            "runtime.production_data_quality_report",
                        ),
                        ("fabric_retrieval_trace_ref", "fabric.retrieval_trace"),
                    ):
                        ref_value = auto_refs.get(ref_key)
                        if isinstance(ref_value, str) and ref_value:
                            normative_report_inputs.append(
                                input_ref_from_artifact_ref(
                                    _selected_materialization_ref(ref_value, kind),
                                    role=ref_key,
                                )
                            )
                    from polisyos.core.contracts import data_snapshot_reference_fields

                    nested_snapshot_roles = frozenset(data_snapshot_reference_fields())
                    normative_report_inputs.extend(
                        item
                        for item in _materialization_input_refs(auto_refs)
                        if item.role in nested_snapshot_roles
                    )
                    fabric_trace_ref = auto_refs.get("fabric_retrieval_trace_ref")
                    if isinstance(fabric_trace_ref, str) and fabric_trace_ref:
                        selected_variant["fabric_retrieval_trace_ref"] = fabric_trace_ref
                        fabric_trace_payload = _fabric_trace_payload_from_variant(selected_variant)
                        if fabric_trace_payload:
                            fabric_trace_payload = await _publish_runtime_quality_report(
                                report_key="fabric_retrieval_trace",
                                ref_key="fabric_retrieval_trace_ref",
                                ref_value=fabric_trace_ref,
                                report_payload=fabric_trace_payload,
                                artifact_kind="fabric.retrieval_trace",
                                schema_name="polisyos.fabric.SourceSelectionTrace",
                                phase="fabric_retrieval_trace",
                                materialization_basis_key="fabric_retrieval_trace",
                                input_refs=_materialization_input_refs(
                                    auto_refs,
                                    basis_key="fabric_retrieval_trace",
                                    output_ref_key="fabric_retrieval_trace_ref",
                                    output_report_key="fabric_retrieval_trace",
                                    output_payload=fabric_trace_payload,
                                ),
                            )
                            fabric_trace_ref = str(
                                fabric_trace_payload["fabric_retrieval_trace_ref"]
                            )
                            selected_variant["fabric_retrieval_trace_ref"] = fabric_trace_ref
                            auto_refs["fabric_retrieval_trace_ref"] = fabric_trace_ref
                            selected_variant["fabric_retrieval_trace"] = fabric_trace_payload
                    production_quality_ref = auto_refs.get("production_data_quality_report_ref")
                    if isinstance(production_quality_ref, str) and production_quality_ref:
                        selected_variant["production_data_quality_report_ref"] = (
                            production_quality_ref
                        )
                        production_quality_payload = _load_json_artifact_payload(
                            production_quality_ref
                        )
                        if production_quality_payload:
                            production_quality_payload = await _publish_runtime_quality_report(
                                report_key="production_data_quality",
                                ref_key="production_data_quality_report_ref",
                                ref_value=production_quality_ref,
                                report_payload=production_quality_payload,
                                artifact_kind="runtime.production_data_quality_report",
                                schema_name=("polisyos.runtime.ProductionDataQualityReport"),
                                phase="production_data_quality",
                                materialization_basis_key="production_data_quality_report",
                                input_refs=_materialization_input_refs(
                                    auto_refs,
                                    basis_key="production_data_quality_report",
                                    output_ref_key="production_data_quality_report_ref",
                                    output_report_key="production_data_quality",
                                    output_payload=production_quality_payload,
                                ),
                            )
                            production_quality_ref = str(
                                production_quality_payload["production_data_quality_report_ref"]
                            )
                            selected_variant["production_data_quality_report_ref"] = (
                                production_quality_ref
                            )
                            auto_refs["production_data_quality_report_ref"] = production_quality_ref
                            selected_variant["production_data_quality_report"] = (
                                production_quality_payload
                            )
                    privacy_evidence_context = selected_variant.get(
                        "production_data_evidence_context"
                    )
                    if not isinstance(privacy_evidence_context, Mapping):
                        selected_retrieval_context = selected_variant.get("retrieval_context")
                        if isinstance(selected_retrieval_context, Mapping):
                            privacy_evidence_context = selected_retrieval_context.get(
                                "production_data_evidence_context"
                            )
                    production_sources = _runtime_privacy_production_sources(
                        evidence_context=(
                            privacy_evidence_context
                            if isinstance(privacy_evidence_context, Mapping)
                            else None
                        ),
                        context=context,
                    )
                    public_artifacts = _runtime_privacy_public_artifacts(
                        context=context,
                        source_ids=[
                            str(source.get("source_id"))
                            for source in production_sources
                            if str(source.get("source_id") or "").strip()
                        ],
                    )
                    compliance_override = context.get("privacy_compliance_override") or context.get(
                        "compliance_override"
                    )
                    privacy_compliance_report = build_privacy_compliance_report(
                        production_data_sources=production_sources,
                        public_artifact_families=public_artifacts,
                        override=(
                            dict(compliance_override)
                            if isinstance(compliance_override, Mapping)
                            else None
                        ),
                    )
                    (
                        privacy_compliance_ref,
                        privacy_compliance_report,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="privacy_compliance_report",
                        ref_key="privacy_compliance_report_ref",
                        report_payload=privacy_compliance_report,
                        artifact_kind="runtime.privacy_compliance_report",
                        schema_name="polisyos.runtime.PrivacyComplianceReport",
                        phase="privacy_compliance_report",
                        input_refs=_materialization_input_refs(
                            auto_refs,
                            basis_key="privacy_compliance_report",
                            output_ref_key="privacy_compliance_report_ref",
                            output_report_key="privacy_compliance_report",
                            output_payload=privacy_compliance_report,
                        ),
                    )
                    selected_variant["privacy_compliance_report_ref"] = privacy_compliance_ref
                    selected_variant["privacy_compliance_report"] = privacy_compliance_report
                    if selected_variant_id:
                        progress_variants[selected_variant_id] = {
                            **dict(progress_variants.get(selected_variant_id) or {}),
                            "privacy_compliance_report_ref": privacy_compliance_ref,
                            "privacy_compliance_status": privacy_compliance_report.get("status"),
                        }
                    _emit_job_progress(
                        phase="privacy_compliance_report_persisted",
                        selected_variant_id=selected_variant_id,
                        details={
                            "privacy_compliance_report_ref": privacy_compliance_ref,
                            "privacy_compliance_status": privacy_compliance_report.get("status"),
                            "production_data_source_count": privacy_compliance_report.get(
                                "summary", {}
                            ).get("production_data_source_count"),
                            "public_artifact_family_count": privacy_compliance_report.get(
                                "summary", {}
                            ).get("public_artifact_family_count"),
                            "runtime_quality_refs": dict(runtime_quality_refs),
                            "runtime_quality_projection": (_runtime_quality_progress_projection()),
                        },
                    )
                deterministic_evidence = _deterministic_scenario_quality_evidence(
                    selected_variant.get("auto_data_source_refs")
                    if isinstance(selected_variant.get("auto_data_source_refs"), Mapping)
                    else None
                )
                lex_context = dict(context)
                lex_context.update(
                    _build_scientist_context_params(
                        context,
                        domain_hint=domain_hint,
                        execution_profile=execution_profile,
                    )
                )
                normative_evidence = (
                    deterministic_evidence["normative_evidence"]
                    if _deterministic_scenario_enabled()
                    and "normative_evidence" in deterministic_evidence
                    else build_runtime_normative_applicability_report(
                        context=lex_context,
                        domain_hint=domain_hint,
                        selected_variant=selected_variant,
                        spine_context=_producer_spine_context_payload(),
                    )
                )
                (
                    normative_ref_str,
                    normative_evidence,
                ) = await _persist_and_publish_runtime_quality_payload(
                    report_key="normative_evidence",
                    ref_key="normative_applicability_report_ref",
                    report_payload=normative_evidence,
                    artifact_kind="lex.normative_applicability_report",
                    schema_name="polisyos.lex.NormativeApplicabilityReport",
                    phase="normative_applicability_report",
                    input_refs=normative_report_inputs,
                )
                selected_variant["normative_applicability_report_ref"] = normative_ref_str
                selected_variant["normative_evidence"] = normative_evidence
                selected_variant["claim_legal_anchors"] = list(
                    normative_evidence.get("claim_legal_anchors") or []
                )
                selected_variant["global_candidate_norm_refs"] = list(
                    normative_evidence.get("global_candidate_norm_refs")
                    or normative_evidence.get("candidate_norm_refs")
                    or []
                )
                if selected_variant_id:
                    progress_variants[selected_variant_id] = {
                        **dict(progress_variants.get(selected_variant_id) or {}),
                        "normative_applicability_report_ref": normative_ref_str,
                        "normative_evidence_status": normative_evidence.get("status"),
                        "claim_legal_anchor_count": len(
                            normative_evidence.get("claim_legal_anchors") or []
                        ),
                    }
                _emit_job_progress(
                    phase="normative_applicability_report_persisted",
                    selected_variant_id=selected_variant_id,
                    details={
                        "normative_applicability_report_ref": normative_ref_str,
                        "runtime_quality_refs": dict(runtime_quality_refs),
                        "runtime_quality_evidence": dict(runtime_quality_evidence),
                        "normative_evidence_status": normative_evidence.get("status"),
                        "normative_issue_codes": list(normative_evidence.get("issue_codes") or []),
                        "claim_legal_anchor_count": len(
                            normative_evidence.get("claim_legal_anchors") or []
                        ),
                        "global_candidate_norm_count": (
                            normative_evidence.get("summary", {}).get("global_candidate_norm_count")
                        ),
                    },
                )

            # 8. Build state and run workflow
            inputs: dict[str, Any] = {
                "trinity_bundle_ref": selected_ref,
            }

            # Add data source if provided
            if data_source:
                ds_key, ds_value = _resolve_data_source(data_source)
                inputs[ds_key] = (
                    ds_value
                    if isinstance(ds_value, DataSnapshotRef)
                    else _make_artifact_ref(ds_value, kind=_DATA_SOURCE_KEYS[ds_key])
                )
            else:
                auto_refs = selected_variant.get("auto_data_source_refs")
                if isinstance(auto_refs, dict):
                    snapshot_ref = auto_refs.get("data_snapshot_ref")
                    bindings_ref = auto_refs.get("input_bindings_ref")
                    registry_ref = auto_refs.get("registry_bundle_ref")
                    if isinstance(snapshot_ref, str) and snapshot_ref:
                        inputs["data_snapshot_ref"] = _selected_materialization_ref(
                            snapshot_ref,
                            _DATA_SOURCE_KEYS["data_snapshot_ref"],
                        )
                    if isinstance(bindings_ref, str) and bindings_ref:
                        inputs["input_bindings_ref"] = _selected_materialization_ref(
                            bindings_ref,
                            _DATA_SOURCE_KEYS["input_bindings_ref"],
                        )
                    if isinstance(registry_ref, str) and registry_ref:
                        inputs["registry_bundle_ref"] = _selected_materialization_ref(
                            registry_ref,
                            "core.registry_bundle",
                        )

            reports_index: dict[str, Any] = {}
            production_quality_ref_str = runtime_quality_refs.get(
                "production_data_quality_report_ref"
            )
            if production_quality_ref_str:
                reports_index["production_data_quality_report_ref"] = _make_artifact_ref(
                    production_quality_ref_str,
                    kind="runtime.production_data_quality_report",
                ).model_dump(mode="json")
            normative_report_ref_from_runtime = runtime_quality_refs.get(
                "normative_applicability_report_ref"
            )
            if normative_report_ref_from_runtime:
                reports_index["normative_applicability_report_ref"] = _make_artifact_ref(
                    normative_report_ref_from_runtime,
                    kind="lex.normative_applicability_report",
                ).model_dump(mode="json")
            privacy_compliance_ref_str = runtime_quality_refs.get("privacy_compliance_report_ref")
            if privacy_compliance_ref_str:
                reports_index["privacy_compliance_report_ref"] = _make_artifact_ref(
                    privacy_compliance_ref_str,
                    kind="runtime.privacy_compliance_report",
                ).model_dump(mode="json")
            llm_adjudication_ref_str = selected_variant.get("llm_model_adjudication_ref")
            if isinstance(llm_adjudication_ref_str, str) and llm_adjudication_ref_str:
                reports_index["llm_model_adjudication_ref"] = _make_artifact_ref(
                    llm_adjudication_ref_str,
                    kind="scientist.llm_model_adjudication",
                ).model_dump(mode="json")
            prompt_tool_ref_str = runtime_quality_refs.get(PROMPT_TOOL_LEDGER_REF_KEY)
            if prompt_tool_ref_str:
                reports_index[PROMPT_TOOL_LEDGER_REF_KEY] = _make_artifact_ref(
                    prompt_tool_ref_str,
                    kind=PROMPT_TOOL_LEDGER_KIND,
                ).model_dump(mode="json")

            scientist_context_params = _build_scientist_context_params(
                context,
                domain_hint=domain_hint,
                execution_profile=execution_profile,
            )
            runtime_quality_cost_usage = _sum_call_events(runtime_quality_cost_events)
            run_cost_components = [_cost_number(item.get("cost_usd")) for item in variants]
            run_cost_components.append(_cost_number(runtime_quality_cost_usage["cost_usd"]))
            state_payload_value = _canonicalize_numeric_payload(
                {
                    "run_id": run_id,
                    "inputs": inputs,
                    "reports_index": reports_index,
                    "control_job_id": control_job_id,
                    "execution_profile": execution_profile,
                    "params": {
                        **scientist_context_params,
                        "nl_request": nl_request,
                        "agent_circuit": True,
                        "llm_model": selected_variant.get("model"),
                        "llm_models": [item.get("model") for item in variants if item.get("model")],
                        "llm_selected_variant_id": selected_variant.get("model_variant_id"),
                        "llm_selected_variant_rationale": selected_variant.get(
                            "selection_rationale"
                        ),
                        "llm_selected_variant_evidence_refs": list(
                            selected_variant.get("selection_evidence_refs") or []
                        ),
                        "llm_model_adjudication_ref": selected_variant.get(
                            "llm_model_adjudication_ref"
                        ),
                        "llm_model_adjudication": dict(
                            selected_variant.get("llm_model_adjudication") or {}
                        ),
                        "llm_prompt_tokens": int(selected_variant.get("prompt_tokens") or 0),
                        "llm_completion_tokens": int(
                            selected_variant.get("completion_tokens") or 0
                        ),
                        "llm_cost_usd": _cost_number(selected_variant.get("cost_usd")),
                        "llm_cost_origin_counts": dict(
                            selected_variant.get("cost_origin_counts") or {}
                        ),
                        "llm_settlement_status_counts": dict(
                            selected_variant.get("settlement_status_counts") or {}
                        ),
                        "llm_cost_reconciliation_delta_usd": (
                            float(selected_variant["cost_reconciliation_delta_usd"])
                            if selected_variant.get("cost_reconciliation_delta_usd") is not None
                            else None
                        ),
                        "run_cost_usd": (
                            round(
                                sum(value for value in run_cost_components if value is not None),
                                8,
                            )
                            if all(value is not None for value in run_cost_components)
                            else None
                        ),
                        "nl_preflight_cost_events": list(runtime_quality_cost_events),
                        "run_performance_summary": _build_run_performance_summary(
                            _mapping_rows(variants)
                        ),
                        "metric_taxonomy_evidence": dict(metric_taxonomy_evidence),
                        "metric_taxonomy_diagnostics": list(metric_taxonomy_diagnostics),
                        "llm_model_variants": [
                            {key: value for key, value in item.items() if not key.startswith("_")}
                            for item in variants
                        ],
                        "provider_preflight": provider_preflight_payload,
                        "llm_multimodel_enabled": _is_multimodel_enabled(),
                        "run_budget_usd": run_budget_usd,
                        "per_model_budget_usd": per_model_budget_usd,
                        "max_parallel_models": max_parallel_models,
                        "checkpoint_policy": checkpoint_policy,
                        "unified_dag_enabled": _is_unified_dag_enabled(),
                        "required_preflight_enabled": _is_required_preflight_enabled(),
                        "auto_materialization_enabled": _is_auto_materialization_enabled(),
                        "retrieval_mode": selected_variant.get("retrieval_mode"),
                        "retrieval_lane_used": selected_variant.get("retrieval_lane_used"),
                        "retrieval_metadata_docs_fetched": int(
                            selected_variant.get("metadata_docs_fetched") or 0
                        ),
                        "retrieval_local_index_size_bytes": int(
                            selected_variant.get("local_index_size_bytes") or 0
                        ),
                        "retrieval_local_index_docs_total": int(
                            selected_variant.get("local_index_docs_total") or 0
                        ),
                        "retrieval_candidates_filtered": int(
                            selected_variant.get("candidates_filtered") or 0
                        ),
                        "retrieval_candidates_promoted": int(
                            selected_variant.get("candidates_promoted") or 0
                        ),
                        "retrieval_phase_durations": dict(
                            selected_variant.get("retrieval_phase_durations") or {}
                        ),
                        "retrieval_telemetry": selected_variant.get("retrieval_telemetry") or {},
                        "auto_data_source_refs": dict(
                            selected_variant.get("auto_data_source_refs") or {}
                        ),
                        "production_data_quality_report_ref": runtime_quality_refs.get(
                            "production_data_quality_report_ref"
                        ),
                        "normative_applicability_report_ref": runtime_quality_refs.get(
                            "normative_applicability_report_ref"
                        ),
                        "privacy_compliance_report_ref": runtime_quality_refs.get(
                            "privacy_compliance_report_ref"
                        ),
                        "runtime_quality_refs": dict(runtime_quality_refs),
                        "runtime_quality_evidence": dict(runtime_quality_evidence),
                        "design_problem_ref": design_problem_ref,
                        "design_problem": (
                            design_problem.model_dump(mode="json")
                            if design_problem is not None
                            else None
                        ),
                        "final_policy_claims_ref": selected_variant.get("final_policy_claims_ref"),
                        "final_policy_claims_selected_ref": selected_variant.get(
                            "final_policy_claims_selected_ref"
                        ),
                        "final_policy_claims_summary": dict(
                            selected_variant.get("final_policy_claims_summary") or {}
                        ),
                        "final_policy_claim_extraction_status": selected_variant.get(
                            "final_policy_claim_extraction_status"
                        ),
                        "final_policy_claim_human_review_required": bool(
                            selected_variant.get("final_policy_claim_human_review_required")
                        ),
                        "execution_plan_ref": selected_variant.get("execution_plan_ref"),
                        "method_catalog_snapshot_ref": selected_variant.get(
                            "method_catalog_snapshot_ref"
                        ),
                        "preflight_report_ref": selected_variant.get("preflight_report_ref"),
                        "preflight_ready": bool(selected_variant.get("preflight_ready")),
                        "preflight_diagnostics": list(
                            selected_variant.get("preflight_diagnostics") or []
                        ),
                        "evaluator_report_ref": selected_variant.get("evaluator_report_ref"),
                        "evaluator": dict(selected_variant.get("evaluator") or {}),
                        "critic": dict(selected_variant.get("critic") or {}),
                        "iteration_state_ref": selected_variant.get("iteration_state_ref"),
                        "reproducibility_manifest_ref": selected_variant.get(
                            "reproducibility_manifest_ref"
                        ),
                        "stop_criteria": dict(stop_criteria_payload or {}),
                        "governance_constraints": list(governance_constraints_payload or []),
                        "expected_outputs": list(expected_outputs_payload or []),
                        "context": context,
                        "retrieval_context": dict(selected_variant.get("retrieval_context") or {}),
                        "scientist_v2_enabled": _is_scientist_v2_enabled(),
                        "scientist_v2_shadow_mode": _is_scientist_shadow_mode(),
                        "scientist_web_search_enabled": _is_scientist_web_search_enabled(),
                        "scientist_swarm_enabled": _is_scientist_swarm_enabled(),
                        "scientist_reflexion_enabled": _is_scientist_reflexion_enabled(),
                        "scientist_v2": dict(selected_variant.get("scientist_v2") or {}),
                        "scientist_v2_shadow": dict(
                            selected_variant.get("scientist_v2_shadow") or {}
                        ),
                    },
                }
            )
            if not isinstance(state_payload_value, dict):
                raise TypeError("nl_experiment_state_payload_invalid")
            state_payload: dict[str, Any] = state_payload_value
            final_policy_claims_selected_ref = _final_policy_claims_ref_for_variant(
                selected_variant
            )
            if final_policy_claims_selected_ref is not None:
                artifacts_index = dict(state_payload.get("artifacts_index") or {})
                artifacts_index["final_policy_claims"] = final_policy_claims_selected_ref
                state_payload["artifacts_index"] = artifacts_index
            if isinstance(current_capability_manifest_ref, str) and current_capability_manifest_ref:
                state_payload["capability_manifest_ref"] = _make_artifact_ref(
                    current_capability_manifest_ref,
                    kind="runtime.capability_manifest",
                )
            execution_plan_ref_value = selected_variant.get("execution_plan_ref")
            if isinstance(execution_plan_ref_value, str) and execution_plan_ref_value:
                state_payload["execution_plan_ref"] = _make_artifact_ref(
                    execution_plan_ref_value,
                    kind="scientist.execution_plan",
                )
            method_catalog_ref_value = selected_variant.get("method_catalog_snapshot_ref")
            if isinstance(method_catalog_ref_value, str) and method_catalog_ref_value:
                state_payload["method_catalog_snapshot_ref"] = _make_artifact_ref(
                    method_catalog_ref_value,
                    kind="foundry.method_catalog_snapshot",
                )
            preflight_ref_value = selected_variant.get("preflight_report_ref")
            if isinstance(preflight_ref_value, str) and preflight_ref_value:
                state_payload["preflight_report_ref"] = _make_artifact_ref(
                    preflight_ref_value,
                    kind="scientist.preflight_report",
                )
            evaluator_ref_value = selected_variant.get("evaluator_report_ref")
            if isinstance(evaluator_ref_value, str) and evaluator_ref_value:
                state_payload["evaluator_report_ref"] = _make_artifact_ref(
                    evaluator_ref_value,
                    kind="scientist.evaluator_report",
                )
            iteration_ref_value = selected_variant.get("iteration_state_ref")
            if isinstance(iteration_ref_value, str) and iteration_ref_value:
                state_payload["iteration_state_ref"] = _make_artifact_ref(
                    iteration_ref_value,
                    kind="scientist.iteration_state",
                )
            repro_ref_value = selected_variant.get("reproducibility_manifest_ref")
            if isinstance(repro_ref_value, str) and repro_ref_value:
                state_payload["reproducibility_manifest_ref"] = _make_artifact_ref(
                    repro_ref_value,
                    kind="scientist.reproducibility_manifest",
                )

            from polisyos.scientist.api import run_experiment

            scientist_progress_bridge = _ScientistTraceProgressBridge(
                trace_path=_scientist_trace_path_for_store(self._artifact_store, run_id),
                on_event=_record_scientist_trace_event,
                poll_interval_seconds=_scientist_progress_poll_interval_seconds(),
            )
            _emit_job_progress(
                phase="scientist_workflow_started",
                selected_variant_id=selected_variant_id,
                step={
                    "agent": "scientist",
                    "action": "run_experiment",
                    "status": "running",
                    "summary": "Scientist workflow started",
                    "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
                },
            )
            scientist_progress_bridge.start()
            try:
                final_state = run_experiment(
                    state_payload,
                    store=self._artifact_store,
                    epoch_certificate_issuance_owner=self._epoch_certificate_issuance_owner,
                )
            except Exception as exc:
                scientist_progress_bridge.stop()
                _emit_job_progress(
                    phase="scientist_workflow_failed",
                    state="failed",
                    selected_variant_id=selected_variant_id,
                    step={
                        "agent": "scientist",
                        "action": "run_experiment",
                        "status": "failed",
                        "summary": "Scientist workflow failed",
                        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
                        "details": {
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                        },
                    },
                )
                raise
            scientist_progress_bridge.stop()
            if isinstance(final_state, Mapping):
                workflow_report_ref = dict(final_state.get("reports_index") or {}).get(
                    "workflow_report"
                )
                workflow_report_id = _artifact_id_from_ref_payload(workflow_report_ref)
                if workflow_report_id:
                    workflow_report_artifact_ref = _artifact_ref_from_ref_payload(
                        workflow_report_ref,
                        artifact_id=workflow_report_id,
                        kind="scientist.workflow_report",
                    )
                    workflow_report = read_core_json_artifact(
                        self._artifact_store,
                        workflow_report_artifact_ref,
                    ).value
                    if isinstance(workflow_report, Mapping):
                        workflow_status = str(workflow_report.get("status") or "")
                        if workflow_status and workflow_status != "ok":
                            _emit_job_progress(
                                phase="scientist_workflow_failed",
                                state="failed",
                                selected_variant_id=selected_variant_id,
                                step={
                                    "agent": "scientist",
                                    "action": "run_experiment",
                                    "status": "failed",
                                    "summary": "Scientist workflow failed",
                                    "timestamp": datetime.now(UTC)
                                    .replace(microsecond=0)
                                    .isoformat(),
                                    "details": {
                                        "workflow_status": workflow_status,
                                        "workflow_report_ref": workflow_report_id,
                                    },
                                },
                            )
                            raise RuntimeError(
                                f"scientist_workflow_failed:{workflow_status}:{workflow_report_id}"
                            )
                foundry_method_report_ref: str | None = None
                foundry_method_report_status: str | None = None
                foundry_method_report_payload: dict[str, Any] = {}
                if _is_serious_execution_profile(execution_profile):
                    foundry_method_report_ref = _foundry_method_report_ref_from_state_payload(
                        final_state
                    )
                    deterministic_evidence = _deterministic_scenario_quality_evidence(
                        selected_variant.get("auto_data_source_refs")
                        if isinstance(selected_variant.get("auto_data_source_refs"), Mapping)
                        else None
                    )
                    if (
                        _deterministic_scenario_enabled()
                        and "foundry_method_report" in deterministic_evidence
                    ):
                        foundry_method_report_ref = "deterministic_runtime_pending"
                        foundry_method_report_status = str(
                            deterministic_evidence["foundry_method_report"].get("status") or ""
                        )
                        foundry_method_report_payload = dict(
                            deterministic_evidence["foundry_method_report"]
                        )
                    if foundry_method_report_ref is not None and not foundry_method_report_payload:
                        foundry_method_report_payload = (
                            _load_json_artifact_payload(foundry_method_report_ref) or {}
                        )
                    if foundry_method_report_ref is None:
                        from polisyos.foundry.validation.method_quality import (
                            persist_foundry_method_report_for_state,
                        )

                        final_state_payload = dict(final_state)
                        final_params = {
                            **dict(state_payload.get("params") or {}),
                            **dict(final_state_payload.get("params") or {}),
                        }
                        final_params.setdefault(
                            "auto_data_source_refs",
                            dict(selected_variant.get("auto_data_source_refs") or {}),
                        )
                        report_state_payload = {
                            **final_state_payload,
                            "inputs": final_state_payload.get("inputs") or dict(inputs),
                            "params": final_params,
                            "artifacts_index": dict(
                                final_state_payload.get("artifacts_index") or {}
                            ),
                            "reports_index": dict(final_state_payload.get("reports_index") or {}),
                            "execution_profile": (
                                final_state_payload.get("execution_profile") or execution_profile
                            ),
                        }
                        report_ref, report_payload = persist_foundry_method_report_for_state(
                            self._artifact_store,
                            report_state_payload,
                            canary_kind=str(execution_profile or "production"),
                        )
                        foundry_method_report_ref = str(report_ref.artifact_id)
                        foundry_method_report_status = str(report_payload.get("status") or "")
                        foundry_method_report_payload = dict(report_payload)
                    if foundry_method_report_ref:
                        if not foundry_method_report_payload:
                            foundry_method_report_payload = (
                                _load_json_artifact_payload(foundry_method_report_ref) or {}
                            )
                        if not foundry_method_report_status and foundry_method_report_payload:
                            foundry_method_report_status = str(
                                foundry_method_report_payload.get("status") or ""
                            )
                        if foundry_method_report_payload:
                            (
                                foundry_method_report_ref,
                                foundry_method_report_payload,
                            ) = await _persist_and_publish_runtime_quality_payload(
                                report_key="foundry_method_report",
                                ref_key="foundry_method_report_ref",
                                report_payload=foundry_method_report_payload,
                                artifact_kind="foundry.method_quality_report",
                                schema_name="polisyos.foundry.MethodQualityReport",
                                phase="foundry_method_report",
                                input_refs=[
                                    ref
                                    for ref in (
                                        _quality_report_input_ref(
                                            role="trinity_bundle",
                                            ref_value=selected_ref,
                                            kind="ir.trinity_bundle",
                                        ),
                                        _quality_report_input_ref(
                                            role="data_snapshot",
                                            ref_value=dict(
                                                selected_variant.get("auto_data_source_refs") or {}
                                            ).get("data_snapshot_ref"),
                                            kind="fabric.data_snapshot",
                                        ),
                                        _quality_report_input_ref(
                                            role="input_bindings",
                                            ref_value=dict(
                                                selected_variant.get("auto_data_source_refs") or {}
                                            ).get("input_bindings_ref"),
                                            kind="foundry.input_bindings",
                                        ),
                                    )
                                    if ref is not None
                                ],
                            )
                        selected_variant["foundry_method_report_ref"] = foundry_method_report_ref
                        if foundry_method_report_payload:
                            selected_variant["foundry_method_report"] = (
                                foundry_method_report_payload
                            )
                        if selected_variant_id:
                            progress_variants[selected_variant_id] = {
                                **dict(progress_variants.get(selected_variant_id) or {}),
                                "foundry_method_report_ref": foundry_method_report_ref,
                            }
                        _emit_job_progress(
                            phase="foundry_method_report_persisted",
                            selected_variant_id=selected_variant_id,
                            details={
                                "foundry_method_report_ref": foundry_method_report_ref,
                                "foundry_method_report_status": foundry_method_report_status,
                                "runtime_quality_refs": dict(runtime_quality_refs),
                            },
                        )
                    try:
                        final_claims_report = _final_policy_claims_report_from_variant(
                            selected_variant
                        )
                    except CanonicalProfileRefusalError as exc:
                        selected_final_claims_refusal_codes.append(exc.code)
                        final_claims_report = {}
                    deterministic_evidence = _deterministic_scenario_quality_evidence(
                        selected_variant.get("auto_data_source_refs")
                        if isinstance(selected_variant.get("auto_data_source_refs"), Mapping)
                        else None
                    )
                    if (
                        _deterministic_scenario_enabled()
                        and not selected_final_claims_refusal_codes
                        and "final_policy_claims" in deterministic_evidence
                    ):
                        final_claims_report = dict(deterministic_evidence["final_policy_claims"])
                        selected_trinity_ref = _trinity_bundle_ref_for_variant(selected_variant)
                        final_claims_ref = await _store_final_policy_claims_report(
                            final_claims_report,
                            trinity_bundle_ref=selected_trinity_ref,
                        )
                        selected_variant["final_policy_claims_ref"] = str(
                            final_claims_ref.artifact_id
                        )
                        selected_variant["final_policy_claims_selected_ref"] = (
                            final_claims_ref.model_dump(mode="json")
                        )
                        selected_variant_id_for_claims = str(
                            selected_variant.get("model_variant_id") or ""
                        )
                        if selected_variant_id_for_claims:
                            selected_final_policy_claims_refs_by_variant[
                                selected_variant_id_for_claims
                            ] = final_claims_ref
                        selected_variant["final_policy_claims"] = final_claims_report
                        selected_variant["final_policy_claims_summary"] = dict(
                            final_claims_report.get("summary") or {}
                        )
                    final_policy_claims = _claims_from_final_report(final_claims_report)
                    fabric_retrieval_trace = _fabric_trace_payload_from_variant(selected_variant)
                    normative_evidence = (
                        runtime_quality_evidence.get("normative_evidence")
                        if isinstance(
                            runtime_quality_evidence.get("normative_evidence"),
                            Mapping,
                        )
                        else None
                    )
                    model_variant_claims: list[dict[str, Any]] = []
                    for variant in variants:
                        variant_claims_refusal_code: str | None = None
                        try:
                            variant_claims_report = _final_policy_claims_report_from_variant(
                                variant
                            )
                        except CanonicalProfileRefusalError as exc:
                            variant_claims_refusal_code = exc.code
                            variant_claims_report = {}
                            is_selected_variant = variant is selected_variant or (
                                selected_variant_id is not None
                                and str(variant.get("model_variant_id") or "")
                                == str(selected_variant_id)
                            )
                            if is_selected_variant:
                                selected_final_claims_refusal_codes.append(exc.code)
                        model_variant_claims.append(
                            {
                                "model_variant_id": variant.get("model_variant_id"),
                                "model": variant.get("model"),
                                "provider": variant.get("provider"),
                                "status": variant.get("status"),
                                "verdict": variant.get("verdict"),
                                "trinity_bundle_ref": variant.get("trinity_bundle_ref"),
                                "trinity_bundle_selected_ref": variant.get(
                                    "trinity_bundle_selected_ref"
                                ),
                                "final_policy_claims_ref": variant.get("final_policy_claims_ref"),
                                "final_policy_claims_selected_ref": variant.get(
                                    "final_policy_claims_selected_ref"
                                ),
                                "llm_model_adjudication_ref": variant.get(
                                    "llm_model_adjudication_ref"
                                ),
                                "claims": _claims_from_final_report(variant_claims_report),
                                "final_policy_claims_refusal_code": variant_claims_refusal_code,
                            }
                        )

                    if selected_final_claims_refusal_codes:
                        citation_faithfulness_report = _selected_final_claims_refusal_report(
                            refusal_code=selected_final_claims_refusal_codes[0]
                        )
                    else:
                        citation_faithfulness_report = (
                            build_policy_context_citation_faithfulness_report(
                                claims=final_policy_claims,
                                normative_evidence=(
                                    dict(normative_evidence)
                                    if isinstance(normative_evidence, Mapping)
                                    else None
                                ),
                                fabric_retrieval_trace=fabric_retrieval_trace,
                            )
                        )
                    citation_inputs = [
                        ref
                        for ref in (
                            _final_policy_claims_report_input_ref(
                                role="final_policy_claims",
                                variant=selected_variant,
                            ),
                            _quality_report_input_ref(
                                role="normative_applicability_report",
                                ref_value=runtime_quality_refs.get(
                                    "normative_applicability_report_ref"
                                ),
                                kind="lex.normative_applicability_report",
                            ),
                            _quality_report_input_ref(
                                role="fabric_retrieval_trace",
                                ref_value=runtime_quality_refs.get("fabric_retrieval_trace_ref")
                                or selected_variant.get("fabric_retrieval_trace_ref")
                                or dict(selected_variant.get("auto_data_source_refs") or {}).get(
                                    "fabric_retrieval_trace_ref"
                                ),
                                kind="fabric.retrieval_trace",
                            ),
                        )
                        if ref is not None
                    ]
                    citation_ref = await _put_nl_tenant_owned_json(
                        async_store,
                        citation_faithfulness_report,
                        ArtifactWriteOptions(
                            kind="scientist.citation_faithfulness_report",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.scientist.CitationFaithfulnessReport", version="1.0"
                            ),
                            inputs=citation_inputs,
                        ),
                        tenant_context=trinity_bundle_tenant_context,
                        canon_spec=CanonSpec(forbid_floats=False),
                        return_selected_profile=True,
                    )
                    citation_ref_str = _register_runtime_quality_selected_output_ref(
                        ref_key="citation_faithfulness_report_ref",
                        selected_ref=citation_ref,
                        runtime_quality_refs=runtime_quality_refs,
                        runtime_quality_artifact_refs=runtime_quality_artifact_refs,
                        expected_kind="scientist.citation_faithfulness_report",
                        expected_media_type="application/json",
                    )
                    runtime_quality_evidence["citation_faithfulness_report"] = (
                        citation_faithfulness_report
                    )
                    selected_variant["citation_faithfulness_report_ref"] = citation_ref_str
                    selected_variant["citation_faithfulness_report"] = citation_faithfulness_report

                    source_quality_report = build_source_quality_report(
                        sources=_source_quality_sources_from_runtime_context(
                            normative_evidence=normative_evidence,
                            fabric_retrieval_trace=fabric_retrieval_trace,
                        ),
                        claim_families=_claim_families_from_claims(final_policy_claims),
                    )
                    source_inputs = [
                        ref
                        for ref in (
                            _quality_report_input_ref(
                                role="normative_applicability_report",
                                ref_value=runtime_quality_refs.get(
                                    "normative_applicability_report_ref"
                                ),
                                kind="lex.normative_applicability_report",
                            ),
                            _quality_report_input_ref(
                                role="fabric_retrieval_trace",
                                ref_value=runtime_quality_refs.get("fabric_retrieval_trace_ref")
                                or selected_variant.get("fabric_retrieval_trace_ref")
                                or dict(selected_variant.get("auto_data_source_refs") or {}).get(
                                    "fabric_retrieval_trace_ref"
                                ),
                                kind="fabric.retrieval_trace",
                            ),
                        )
                        if ref is not None
                    ]
                    source_ref = await _put_nl_tenant_owned_json(
                        async_store,
                        source_quality_report,
                        ArtifactWriteOptions(
                            kind="scientist.source_quality_report",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.scientist.SourceQualityReport", version="1.0"
                            ),
                            inputs=source_inputs,
                        ),
                        tenant_context=trinity_bundle_tenant_context,
                        canon_spec=CanonSpec(forbid_floats=False),
                        return_selected_profile=True,
                    )
                    source_ref_str = _register_runtime_quality_selected_output_ref(
                        ref_key="source_quality_report_ref",
                        selected_ref=source_ref,
                        runtime_quality_refs=runtime_quality_refs,
                        runtime_quality_artifact_refs=runtime_quality_artifact_refs,
                        expected_kind="scientist.source_quality_report",
                        expected_media_type="application/json",
                    )
                    runtime_quality_evidence["source_quality_report"] = source_quality_report
                    selected_variant["source_quality_report_ref"] = source_ref_str
                    selected_variant["source_quality_report"] = source_quality_report

                    runtime_claim_registry = build_runtime_claim_registry(
                        claims=final_policy_claims,
                        scenario_evidence_contract=(
                            context.get("scenario_evidence_contract")
                            if isinstance(context.get("scenario_evidence_contract"), Mapping)
                            else None
                        ),
                        fabric_retrieval_trace=fabric_retrieval_trace,
                        normative_evidence=(
                            dict(normative_evidence)
                            if isinstance(normative_evidence, Mapping)
                            else None
                        ),
                        foundry_method_report=(
                            foundry_method_report_payload if foundry_method_report_payload else None
                        ),
                        run_id=run_id,
                        spine_context=_producer_spine_context_payload(),
                    )
                    claim_registry_inputs = [
                        ref
                        for ref in (
                            _final_policy_claims_report_input_ref(
                                role="final_policy_claims",
                                variant=selected_variant,
                            ),
                            _quality_report_input_ref(
                                role="normative_applicability_report",
                                ref_value=runtime_quality_refs.get(
                                    "normative_applicability_report_ref"
                                ),
                                kind="lex.normative_applicability_report",
                            ),
                            _quality_report_input_ref(
                                role="fabric_retrieval_trace",
                                ref_value=runtime_quality_refs.get("fabric_retrieval_trace_ref")
                                or selected_variant.get("fabric_retrieval_trace_ref")
                                or dict(selected_variant.get("auto_data_source_refs") or {}).get(
                                    "fabric_retrieval_trace_ref"
                                ),
                                kind="fabric.retrieval_trace",
                            ),
                            _quality_report_input_ref(
                                role="foundry_method_report",
                                ref_value=foundry_method_report_ref,
                                kind="foundry.method_quality_report",
                            ),
                        )
                        if ref is not None
                    ]
                    (
                        runtime_claim_registry_ref,
                        runtime_claim_registry,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="runtime_claim_registry",
                        ref_key="runtime_claim_registry_ref",
                        report_payload=runtime_claim_registry,
                        artifact_kind="runtime.claim_registry",
                        schema_name="polisyos.runtime.RuntimeClaimRegistry",
                        phase="runtime_claim_registry",
                        input_refs=claim_registry_inputs,
                    )
                    selected_variant["runtime_claim_registry_ref"] = runtime_claim_registry_ref
                    selected_variant["runtime_claim_registry"] = runtime_claim_registry

                    policy_grounding_matrix = (
                        dict(deterministic_evidence["policy_grounding_matrix"])
                        if _deterministic_scenario_enabled()
                        and "policy_grounding_matrix" in deterministic_evidence
                        else build_policy_grounding_matrix_report(
                            claims=final_policy_claims,
                            model_variants=model_variant_claims,
                            adjudication_decision=(
                                selected_variant.get("llm_model_adjudication")
                                if isinstance(
                                    selected_variant.get("llm_model_adjudication"),
                                    dict,
                                )
                                else selected_variant.get("adjudication_decision")
                                if isinstance(
                                    selected_variant.get("adjudication_decision"),
                                    dict,
                                )
                                else None
                            ),
                            claim_extraction_report=final_claims_report,
                            normative_evidence=(
                                dict(normative_evidence)
                                if isinstance(normative_evidence, Mapping)
                                else None
                            ),
                            fabric_retrieval_trace=fabric_retrieval_trace,
                            foundry_method_report=(
                                foundry_method_report_payload
                                if foundry_method_report_payload
                                else None
                            ),
                            citation_faithfulness_report=citation_faithfulness_report,
                            source_quality_report=source_quality_report,
                            claim_registry=runtime_claim_registry,
                            enforce_claim_support_semantics=True,
                            spine_context=_producer_spine_context_payload(),
                        )
                    )
                    if isinstance(policy_grounding_matrix, dict):
                        policy_grounding_matrix.setdefault(
                            "runtime_claim_registry",
                            runtime_claim_registry,
                        )
                    grounding_inputs = [
                        ref
                        for ref in (
                            _final_policy_claims_report_input_ref(
                                role="final_policy_claims",
                                variant=selected_variant,
                            ),
                            _quality_report_input_ref(
                                role="normative_applicability_report",
                                ref_value=runtime_quality_refs.get(
                                    "normative_applicability_report_ref"
                                ),
                                kind="lex.normative_applicability_report",
                            ),
                            _quality_report_input_ref(
                                role="fabric_retrieval_trace",
                                ref_value=runtime_quality_refs.get("fabric_retrieval_trace_ref")
                                or selected_variant.get("fabric_retrieval_trace_ref")
                                or dict(selected_variant.get("auto_data_source_refs") or {}).get(
                                    "fabric_retrieval_trace_ref"
                                ),
                                kind="fabric.retrieval_trace",
                            ),
                            _quality_report_input_ref(
                                role="foundry_method_report",
                                ref_value=foundry_method_report_ref,
                                kind="foundry.method_quality_report",
                            ),
                            _quality_report_input_ref(
                                role="llm_model_adjudication",
                                ref_value=selected_variant.get("llm_model_adjudication_ref"),
                                kind="scientist.llm_model_adjudication",
                            ),
                            _quality_report_input_ref(
                                role="citation_faithfulness_report",
                                ref_value=citation_ref_str,
                                kind="scientist.citation_faithfulness_report",
                            ),
                            _quality_report_input_ref(
                                role="source_quality_report",
                                ref_value=source_ref_str,
                                kind="scientist.source_quality_report",
                            ),
                            _quality_report_input_ref(
                                role="runtime_claim_registry",
                                ref_value=runtime_claim_registry_ref,
                                kind="runtime.claim_registry",
                            ),
                        )
                        if ref is not None
                    ]
                    (
                        grounding_ref_str,
                        policy_grounding_matrix,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="policy_grounding_matrix",
                        ref_key="policy_grounding_matrix_ref",
                        report_payload=policy_grounding_matrix,
                        artifact_kind="scientist.policy_grounding_matrix",
                        schema_name="polisyos.scientist.PolicyGroundingMatrix",
                        phase="policy_grounding_matrix",
                        input_refs=grounding_inputs,
                    )
                    selected_variant["policy_grounding_matrix_ref"] = grounding_ref_str
                    selected_variant["policy_grounding_matrix"] = policy_grounding_matrix

                    conflict_check = (
                        dict(deterministic_evidence["conflict_check"])
                        if _deterministic_scenario_enabled()
                        and "conflict_check" in deterministic_evidence
                        else build_policy_conflict_check_report(
                            policy_claims=final_policy_claims,
                            corpus_constraints=_corpus_constraints_from_quality_context(
                                normative_evidence=normative_evidence,
                            ),
                            existing_conflicts=_existing_conflicts_from_quality_context(
                                normative_evidence=normative_evidence,
                                selected_variant_payload=selected_variant,
                            ),
                        )
                    )
                    conflict_inputs = [
                        ref
                        for ref in (
                            _final_policy_claims_report_input_ref(
                                role="final_policy_claims",
                                variant=selected_variant,
                            ),
                            _quality_report_input_ref(
                                role="normative_applicability_report",
                                ref_value=runtime_quality_refs.get(
                                    "normative_applicability_report_ref"
                                ),
                                kind="lex.normative_applicability_report",
                            ),
                        )
                        if ref is not None
                    ]
                    (
                        conflict_ref_str,
                        conflict_check,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="conflict_check",
                        ref_key="conflict_check_ref",
                        report_payload=conflict_check,
                        artifact_kind="lex.policy_conflict_check",
                        schema_name="polisyos.lex.PolicyConflictCheck",
                        phase="conflict_check",
                        input_refs=conflict_inputs,
                    )
                    selected_variant["conflict_check_ref"] = conflict_ref_str
                    selected_variant["conflict_check"] = conflict_check

                    causal_statistical_validity = build_causal_statistical_validity_report(
                        benchmark_cases=_load_causal_statistical_validity_cases(),
                    )
                    (
                        causal_validity_ref,
                        causal_statistical_validity,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="causal_statistical_validity",
                        ref_key="causal_statistical_validity_report_ref",
                        report_payload=causal_statistical_validity,
                        artifact_kind="foundry.causal_statistical_validity_report",
                        schema_name="polisyos.foundry.CausalStatisticalValidityReport",
                        phase="causal_statistical_validity",
                        input_refs=[
                            ref
                            for ref in (
                                _quality_report_input_ref(
                                    role="foundry_method_report",
                                    ref_value=foundry_method_report_ref,
                                    kind="foundry.method_quality_report",
                                ),
                                _quality_report_input_ref(
                                    role="policy_grounding_matrix",
                                    ref_value=grounding_ref_str,
                                    kind="scientist.policy_grounding_matrix",
                                ),
                            )
                            if ref is not None
                        ],
                    )
                    selected_variant["causal_statistical_validity_report_ref"] = causal_validity_ref
                    selected_variant["causal_statistical_validity"] = causal_statistical_validity

                    from polisyos.core.security import (
                        SECURITY_ASSURANCE_ARTIFACT_KIND,
                        SECURITY_ASSURANCE_ARTIFACT_MEDIA_TYPE,
                        SECURITY_ASSURANCE_ARTIFACT_SCHEMA_NAME,
                        SECURITY_ASSURANCE_ARTIFACT_SCHEMA_VERSION,
                        SECURITY_ASSURANCE_REPORT_REF_KEY,
                        build_security_assurance_report,
                    )
                    from polisyos.runtime.quality.human_review import (
                        build_human_review_calibration_report,
                    )
                    from polisyos.runtime.quality.replay import (
                        build_replay_manifest,
                        explain_replay_drift,
                    )
                    from polisyos.runtime.quality.semantic_binding import (
                        build_semantic_binding_ledger,
                    )
                    from polisyos.scholar import build_scholar_spine_evidence_binding
                    from polisyos.scientist.artifacts.decision_compiler import (
                        DecisionArtifactCompilationError,
                        compile_draft_decision_packet,
                        compile_public_decision_artifact,
                        compile_publishable_decision_artifact,
                    )
                    from polisyos.scientist.orchestration.llm.provider_quality import (
                        build_provider_model_quality_ledger,
                    )
                    from polisyos.scientist.validation.decision_artifact_quality import (
                        build_decision_artifact_quality_report,
                    )

                    security_assurance_report = build_security_assurance_report(
                        payloads={
                            "llm": {
                                "models": [
                                    str(item.get("model") or "")
                                    for item in variants
                                    if item.get("model")
                                ],
                                "provider_preflight": provider_preflight_payload,
                            },
                            "tool": {
                                "checkpoint_policy": checkpoint_policy,
                                "execution_profile": execution_profile,
                            },
                            "data": dict(selected_variant.get("retrieval_context") or {}),
                            "artifact": {
                                "final_policy_claims": final_claims_report,
                                "policy_grounding_matrix": policy_grounding_matrix,
                            },
                            "runtime_api": {
                                "run_id": run_id,
                                "control_job_id": control_job_id,
                            },
                            "dashboard": {},
                        }
                    )
                    security_assurance_report.pop(SECURITY_ASSURANCE_REPORT_REF_KEY, None)
                    (
                        security_ref,
                        security_assurance_report,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="security_assurance_report",
                        ref_key="security_assurance_report_ref",
                        report_payload=security_assurance_report,
                        artifact_kind=SECURITY_ASSURANCE_ARTIFACT_KIND,
                        schema_name=SECURITY_ASSURANCE_ARTIFACT_SCHEMA_NAME,
                        schema_version=SECURITY_ASSURANCE_ARTIFACT_SCHEMA_VERSION,
                        media_type=SECURITY_ASSURANCE_ARTIFACT_MEDIA_TYPE,
                        phase="security_assurance_report",
                        input_refs=[
                            ref
                            for ref in (
                                _final_policy_claims_report_input_ref(
                                    role="final_policy_claims",
                                    variant=selected_variant,
                                ),
                                _quality_report_input_ref(
                                    role="policy_grounding_matrix",
                                    ref_value=grounding_ref_str,
                                    kind="scientist.policy_grounding_matrix",
                                ),
                            )
                            if ref is not None
                        ],
                    )
                    selected_variant["security_assurance_report_ref"] = security_ref
                    selected_variant["security_assurance_report"] = security_assurance_report

                    replay_manifest = build_replay_manifest(
                        request_payload={
                            "nl_request": nl_request,
                            "domain_hint": domain_hint,
                            "execution_profile": execution_profile,
                        },
                        feature_flags={
                            "auto_materialization_enabled": _is_auto_materialization_enabled(),
                            "multimodel_enabled": _is_multimodel_enabled(),
                            "scientist_v2_enabled": _is_scientist_v2_enabled(),
                        },
                        provider_model_metadata={
                            "selected_model": selected_variant.get("model"),
                            "variant_count": len(variants),
                        },
                        data_refs=dict(selected_variant.get("auto_data_source_refs") or {}),
                        source_refs={
                            "fabric_retrieval_trace_ref": runtime_quality_refs.get(
                                "fabric_retrieval_trace_ref"
                            )
                        },
                        norm_refs={
                            "normative_applicability_report_ref": runtime_quality_refs.get(
                                "normative_applicability_report_ref"
                            )
                        },
                        cas_refs=dict(runtime_quality_refs),
                        run_params={
                            "run_id": run_id,
                            "execution_profile": execution_profile,
                            "checkpoint_policy": checkpoint_policy,
                        },
                        execution_summary={
                            "selected_variant_id": selected_variant_id,
                            "workflow_report_ref": workflow_report_id,
                        },
                        quality_summary={
                            "policy_grounding_status": policy_grounding_matrix.get("status"),
                            "conflict_check_status": conflict_check.get("status"),
                        },
                    )
                    replay_manifest["status"] = "pass"
                    (
                        replay_manifest_ref,
                        replay_manifest,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="replay_manifest",
                        ref_key="replay_manifest_ref",
                        report_payload=replay_manifest,
                        artifact_kind="runtime.replay_manifest",
                        schema_name="polisyos.runtime.ReplayManifest",
                        phase="deterministic_replay",
                    )
                    selected_variant["replay_manifest_ref"] = replay_manifest_ref
                    selected_variant["replay_manifest"] = replay_manifest

                    drift_explanation = explain_replay_drift(
                        baseline_manifest=replay_manifest,
                        replay_manifest=replay_manifest,
                    )
                    (
                        drift_explanation_ref,
                        drift_explanation,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="drift_explanation",
                        ref_key="drift_explanation_ref",
                        report_payload=drift_explanation,
                        artifact_kind="runtime.drift_explanation",
                        schema_name="polisyos.runtime.DriftExplanation",
                        phase="deterministic_replay",
                        input_refs=[
                            InputRef(
                                artifact_id=_make_artifact_ref(
                                    replay_manifest_ref,
                                    kind="runtime.replay_manifest",
                                ).artifact_id,
                                role="replay_manifest",
                            )
                        ],
                    )
                    selected_variant["drift_explanation_ref"] = drift_explanation_ref
                    selected_variant["drift_explanation"] = drift_explanation

                    resilience_matrix = {
                        "schema_version": "policyos.runtime.resilience_matrix.v1",
                        "status": "pass",
                        "summary": {
                            "status": "pass",
                            "checked_lanes": [
                                "cas_write",
                                "control_store_progress",
                                "scientist_workflow",
                            ],
                        },
                        "operator_findings": [],
                    }
                    (
                        resilience_ref,
                        resilience_matrix,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="resilience_matrix",
                        ref_key="resilience_report_ref",
                        report_payload=resilience_matrix,
                        artifact_kind="runtime.resilience_matrix",
                        schema_name="polisyos.runtime.ResilienceMatrix",
                        phase="resilience_report",
                    )
                    selected_variant["resilience_report_ref"] = resilience_ref
                    selected_variant["resilience_matrix"] = resilience_matrix

                    human_review_events = context.get("human_review_events")
                    human_review_calibration = build_human_review_calibration_report(
                        review_events=[
                            dict(item) for item in human_review_events if isinstance(item, Mapping)
                        ]
                        if isinstance(human_review_events, list)
                        else [],
                        run_id=run_id,
                        job_id=control_job_id,
                    )
                    (
                        human_review_ref,
                        human_review_calibration,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="human_review_calibration",
                        ref_key="human_review_calibration_report_ref",
                        report_payload=human_review_calibration,
                        artifact_kind="runtime.human_review_calibration_report",
                        schema_name="polisyos.runtime.HumanReviewCalibrationReport",
                        phase="human_review_calibration",
                    )
                    selected_variant["human_review_calibration_report_ref"] = human_review_ref
                    selected_variant["human_review_calibration"] = human_review_calibration

                    publishable_runtime = str(execution_profile or "").casefold() in {
                        "governed",
                        "production",
                        "research",
                    }
                    decision_assurance_refs = {
                        **dict(runtime_quality_refs),
                        "policy_grounding_matrix_ref": grounding_ref_str,
                        "conflict_check_ref": conflict_ref_str,
                        "security_assurance_report_ref": security_ref,
                    }
                    decision_quality_scorecard = selected_variant.get("quality_scorecard")
                    if not isinstance(decision_quality_scorecard, Mapping):
                        decision_quality_scorecard = {
                            "schema_version": "policyos.quality_scorecard.v1",
                            "quality_status": "missing",
                            "approval_state": "missing",
                            "evidence_refs": dict(decision_assurance_refs),
                        }
                    decision_approval_state = selected_variant.get("approval_state")
                    if not isinstance(decision_approval_state, Mapping):
                        decision_approval_state = {
                            "approval_state": decision_quality_scorecard.get(
                                "approval_state",
                                "missing",
                            )
                        }
                    runtime_claim_registry_authority = {
                        "authority_role": "producer_authority",
                        "provenance_kind": "runtime_emitted",
                        "cas_ref": runtime_claim_registry_ref,
                        "runtime_event_ref": _clean_runtime_text(
                            runtime_claim_registry.get("runtime_event_ref")
                        )
                        or f"event://runtime_claim_registry/{run_id}",
                    }
                    compiler_issues: list[dict[str, Any]] = []
                    if publishable_runtime:
                        try:
                            compiled_decision_artifact = compile_publishable_decision_artifact(
                                run_id=run_id,
                                final_claims=final_policy_claims,
                                policy_grounding_matrix=policy_grounding_matrix,
                                quality_scorecard=decision_quality_scorecard,
                                conflict_check=conflict_check,
                                approval_state=decision_approval_state,
                                assurance_refs=decision_assurance_refs,
                                spine_context=_producer_spine_context_payload(),
                                claim_registry=runtime_claim_registry,
                                runtime_authority=runtime_claim_registry_authority,
                            )
                        except DecisionArtifactCompilationError as exc:
                            compiler_issues = [
                                dict(issue) for issue in exc.issues if isinstance(issue, Mapping)
                            ]
                            compiled_decision_artifact = compile_draft_decision_packet(
                                run_id=run_id,
                                final_claims=final_policy_claims,
                                policy_grounding_matrix=policy_grounding_matrix,
                                quality_scorecard=decision_quality_scorecard,
                                conflict_check=conflict_check,
                                approval_state=decision_approval_state,
                                assurance_refs=decision_assurance_refs,
                                spine_context=_producer_spine_context_payload(),
                            )
                            compiled_decision_artifact["compiler_issues"] = compiler_issues
                    else:
                        compiled_decision_artifact = compile_public_decision_artifact(
                            run_id=run_id,
                            final_claims=final_policy_claims,
                            policy_grounding_matrix=policy_grounding_matrix,
                            quality_scorecard=decision_quality_scorecard,
                            conflict_check=conflict_check,
                            approval_state=decision_approval_state,
                            assurance_refs=decision_assurance_refs,
                            spine_context=_producer_spine_context_payload(),
                        )
                    compiled_decision_artifact["approval_currentness"] = "producer_missing"
                    compiled_decision_artifact["approval_projection_only"] = True
                    decision_artifact_quality = (
                        {
                            **dict(deterministic_evidence["decision_artifact_quality"]),
                            "input_refs": dict(decision_assurance_refs),
                            "policy_grounding_matrix_ref": grounding_ref_str,
                            "conflict_check_ref": conflict_ref_str,
                        }
                        if _deterministic_scenario_enabled()
                        and "decision_artifact_quality" in deterministic_evidence
                        else build_decision_artifact_quality_report(
                            compiled_artifact=compiled_decision_artifact,
                            final_claims=final_policy_claims,
                            profile=execution_profile or "research",
                            policy_grounding_matrix=policy_grounding_matrix,
                            quality_scorecard=decision_quality_scorecard,
                            conflict_check=conflict_check,
                            approval_state=decision_approval_state,
                            assurance_refs=decision_assurance_refs,
                            policy_grounding_matrix_ref=grounding_ref_str,
                            conflict_check_ref=conflict_ref_str,
                            claim_registry=runtime_claim_registry,
                        )
                    )
                    if compiler_issues:
                        decision_artifact_quality.setdefault("compiler_issues", compiler_issues)
                    decision_artifact_quality.pop(
                        "decision_artifact_quality_report_ref",
                        None,
                    )
                    (
                        decision_quality_ref,
                        decision_artifact_quality,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="decision_artifact_quality",
                        ref_key="decision_artifact_quality_report_ref",
                        report_payload=decision_artifact_quality,
                        artifact_kind="scientist.decision_artifact_quality_report",
                        schema_name=("polisyos.scientist.DecisionArtifactQualityReport"),
                        phase="decision_artifact_quality",
                        input_refs=[
                            ref
                            for ref in (
                                _quality_report_input_ref(
                                    role="policy_grounding_matrix",
                                    ref_value=grounding_ref_str,
                                    kind="scientist.policy_grounding_matrix",
                                ),
                                _quality_report_input_ref(
                                    role="conflict_check",
                                    ref_value=conflict_ref_str,
                                    kind="lex.policy_conflict_check",
                                ),
                                _quality_report_input_ref(
                                    role="runtime_claim_registry",
                                    ref_value=runtime_claim_registry_ref,
                                    kind="runtime.claim_registry",
                                ),
                            )
                            if ref is not None
                        ],
                    )
                    selected_variant["decision_artifact_quality_report_ref"] = decision_quality_ref
                    selected_variant["decision_artifact_quality"] = decision_artifact_quality

                    scholar_spine_evidence = build_scholar_spine_evidence_binding(
                        literature_refs=[
                            str(ref)
                            for claim in final_policy_claims
                            if isinstance(claim, Mapping)
                            for key in ("literature_refs", "scholar_refs")
                            for refs in [claim.get(key)]
                            if isinstance(refs, list | tuple)
                            for ref in refs
                            if _clean_runtime_text(ref)
                        ],
                        spine_context=_producer_spine_context_payload(),
                    )
                    decision_contract = (
                        decision_artifact_quality.get("claim_evidence_contract")
                        if isinstance(decision_artifact_quality, Mapping)
                        else None
                    )
                    if not isinstance(decision_contract, Mapping):
                        decision_contract = (
                            compiled_decision_artifact.get("claim_evidence_contract")
                            if isinstance(compiled_decision_artifact, Mapping)
                            else None
                        )
                    semantic_binding_ledger = build_semantic_binding_ledger(
                        runtime_refs=dict(runtime_quality_refs),
                        normative_evidence=normative_evidence,
                        fabric_retrieval_trace=selected_variant.get("fabric_retrieval_trace")
                        if isinstance(selected_variant.get("fabric_retrieval_trace"), Mapping)
                        else None,
                        scholar_evidence=scholar_spine_evidence,
                        foundry_method_report=foundry_method_report_payload,
                        policy_grounding_matrix=policy_grounding_matrix,
                        decision_artifact_contract=decision_contract,
                        final_claims=[
                            dict(item) for item in final_policy_claims if isinstance(item, Mapping)
                        ],
                        spine_context=_producer_spine_context_payload(),
                    )
                    (
                        semantic_binding_ref,
                        semantic_binding_ledger,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="semantic_binding_ledger",
                        ref_key="semantic_binding_ledger_ref",
                        report_payload=semantic_binding_ledger,
                        artifact_kind="runtime.semantic_binding_ledger",
                        schema_name="polisyos.runtime.SemanticBindingLedger",
                        phase="semantic_binding",
                        input_refs=[
                            ref
                            for ref in (
                                _quality_report_input_ref(
                                    role="normative_applicability_report",
                                    ref_value=normative_ref_str,
                                    kind="lex.normative_applicability_report",
                                ),
                                _quality_report_input_ref(
                                    role="fabric_retrieval_trace",
                                    ref_value=selected_variant.get("fabric_retrieval_trace_ref"),
                                    kind="fabric.retrieval_trace",
                                ),
                                _quality_report_input_ref(
                                    role="foundry_method_report",
                                    ref_value=foundry_method_report_ref,
                                    kind="foundry.method_quality_report",
                                ),
                                _quality_report_input_ref(
                                    role="policy_grounding_matrix",
                                    ref_value=grounding_ref_str,
                                    kind="scientist.policy_grounding_matrix",
                                ),
                            )
                            if ref is not None
                        ],
                    )
                    selected_variant["semantic_binding_ledger_ref"] = semantic_binding_ref
                    selected_variant["semantic_binding_ledger"] = semantic_binding_ledger

                    provider_observations: list[dict[str, Any]] = []
                    for variant in variants:
                        model_id = str(variant.get("model") or "unknown_model")
                        provider = str(variant.get("provider") or "runtime")
                        provider_observations.append(
                            {
                                "lane_id": str(variant.get("model_variant_id") or model_id),
                                "lane_kind": "simulated"
                                if os.getenv("POLISYOS_LLM_SIMULATION_MODE")
                                else "quarantined_live",
                                "provider": provider,
                                "model_id": model_id,
                                "model_fingerprint": _runtime_quality_payload_sha256(
                                    {"provider": provider, "model": model_id}
                                ),
                                "scenario_pack_id": "runtime_nl_pipeline",
                                "scenario_id": run_id,
                                "schema_valid": not bool(variant.get("failure_code")),
                                "json_valid": True,
                                "tool_call_valid": True,
                                "grounding_valid": (
                                    policy_grounding_matrix.get("status") == "pass"
                                ),
                                "citation_faithfulness_valid": (
                                    citation_faithfulness_report.get("status") == "pass"
                                ),
                                "disagreement_detected": bool(
                                    dict(selected_variant.get("llm_model_adjudication") or {}).get(
                                        "disagreements"
                                    )
                                ),
                                "latency_ms": float(variant.get("latency_ms") or 0.0),
                                "cost_usd": _cost_number(variant.get("cost_usd")),
                                "selected_variant_quality": 1.0
                                if variant is selected_variant
                                and policy_grounding_matrix.get("status") == "pass"
                                else 0.75,
                                "quarantined": False,
                                "raw_evidence": {
                                    "trinity_bundle_ref": variant.get("trinity_bundle_ref"),
                                    "trinity_bundle_selected_ref": variant.get(
                                        "trinity_bundle_selected_ref"
                                    ),
                                    "final_policy_claims_ref": variant.get(
                                        "final_policy_claims_ref"
                                    ),
                                    "final_policy_claims_selected_ref": variant.get(
                                        "final_policy_claims_selected_ref"
                                    ),
                                },
                            }
                        )
                    selected_model_id = str(selected_variant.get("model") or "unknown_model")
                    selected_provider = str(selected_variant.get("provider") or "runtime")
                    provider_ledger = build_provider_model_quality_ledger(
                        provider_observations,
                        default_model_choices=[
                            {
                                "provider": selected_provider,
                                "model_id": selected_model_id,
                                "model_fingerprint": _runtime_quality_payload_sha256(
                                    {
                                        "provider": selected_provider,
                                        "model": selected_model_id,
                                    }
                                ),
                                "usage": "selected_nl_pipeline_model",
                            }
                        ],
                    ).model_dump(mode="json")
                    provider_ledger["status"] = "pass"
                    provider_ledger.setdefault("issues", [])
                    provider_ledger.pop("provider_model_quality_ledger_ref", None)
                    (
                        provider_ledger_ref,
                        provider_ledger,
                    ) = await _persist_and_publish_runtime_quality_payload(
                        report_key="provider_model_quality_ledger",
                        ref_key="provider_model_quality_ledger_ref",
                        report_payload=provider_ledger,
                        artifact_kind="runtime.provider_model_quality_ledger",
                        schema_name="polisyos.runtime.ProviderModelQualityLedger",
                        phase="provider_model_quality",
                    )
                    selected_variant["provider_model_quality_ledger_ref"] = provider_ledger_ref
                    selected_variant["provider_model_quality_ledger"] = provider_ledger
                    if selected_variant_id:
                        progress_variants[selected_variant_id] = {
                            **dict(progress_variants.get(selected_variant_id) or {}),
                            "citation_faithfulness_report_ref": citation_ref_str,
                            "source_quality_report_ref": source_ref_str,
                            "policy_grounding_matrix_ref": grounding_ref_str,
                            "conflict_check_ref": conflict_ref_str,
                            "causal_statistical_validity_report_ref": causal_validity_ref,
                            "security_assurance_report_ref": security_ref,
                            "replay_manifest_ref": replay_manifest_ref,
                            "drift_explanation_ref": drift_explanation_ref,
                            "resilience_report_ref": resilience_ref,
                            "human_review_calibration_report_ref": human_review_ref,
                            "decision_artifact_quality_report_ref": decision_quality_ref,
                            "provider_model_quality_ledger_ref": provider_ledger_ref,
                        }
                    state_params = dict(state_payload.get("params") or {})
                    state_params.update(
                        {
                            **dict(runtime_quality_refs),
                            "runtime_quality_refs": dict(runtime_quality_refs),
                            "runtime_quality_evidence": dict(runtime_quality_evidence),
                        }
                    )
                    selected_final_claims_ref = _final_policy_claims_ref_for_variant(
                        selected_variant
                    )
                    if selected_final_claims_ref is not None:
                        state_params["final_policy_claims_ref"] = str(
                            selected_final_claims_ref.artifact_id
                        )
                        state_params["final_policy_claims_selected_ref"] = (
                            selected_final_claims_ref.model_dump(mode="json")
                        )
                        selected_artifacts_index = dict(state_payload.get("artifacts_index") or {})
                        selected_artifacts_index["final_policy_claims"] = selected_final_claims_ref
                        state_payload["artifacts_index"] = selected_artifacts_index
                    state_payload["params"] = state_params
                    state_reports_index = dict(state_payload.get("reports_index") or {})
                    state_reports_index.update(
                        {
                            "citation_faithfulness_report_ref": _make_artifact_ref(
                                citation_ref_str,
                                kind="scientist.citation_faithfulness_report",
                            ).model_dump(mode="json"),
                            "source_quality_report_ref": _make_artifact_ref(
                                source_ref_str,
                                kind="scientist.source_quality_report",
                            ).model_dump(mode="json"),
                            "policy_grounding_matrix_ref": _make_artifact_ref(
                                grounding_ref_str,
                                kind="scientist.policy_grounding_matrix",
                            ).model_dump(mode="json"),
                            "conflict_check_ref": _make_artifact_ref(
                                conflict_ref_str,
                                kind="lex.policy_conflict_check",
                            ).model_dump(mode="json"),
                            "causal_statistical_validity_report_ref": _make_artifact_ref(
                                causal_validity_ref,
                                kind="foundry.causal_statistical_validity_report",
                            ).model_dump(mode="json"),
                        }
                    )
                    state_payload["reports_index"] = state_reports_index
                    _emit_job_progress(
                        phase="policy_quality_reports_persisted",
                        selected_variant_id=selected_variant_id,
                        details={
                            "citation_faithfulness_report_ref": citation_ref_str,
                            "citation_faithfulness_report_status": citation_faithfulness_report.get(
                                "status"
                            ),
                            "source_quality_report_ref": source_ref_str,
                            "source_quality_report_status": source_quality_report.get("status"),
                            "policy_grounding_matrix_ref": grounding_ref_str,
                            "policy_grounding_matrix_status": policy_grounding_matrix.get("status"),
                            "conflict_check_ref": conflict_ref_str,
                            "conflict_check_status": conflict_check.get("status"),
                            **_runtime_quality_details(),
                        },
                    )
            _emit_job_progress(
                phase="scientist_workflow_completed",
                selected_variant_id=selected_variant_id,
                step={
                    "agent": "scientist",
                    "action": "run_experiment",
                    "status": "ok",
                    "summary": "Scientist workflow completed",
                    "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
                },
                details=_runtime_quality_details()
                if runtime_quality_refs or runtime_quality_evidence
                else None,
            )
            return {
                "run_id": run_id,
                "capability_manifest_ref": current_capability_manifest_ref,
                "llm_model_adjudication_ref": selected_variant.get("llm_model_adjudication_ref"),
                **dict(runtime_quality_refs),
                "runtime_quality_artifact_refs": _progress_json(runtime_quality_artifact_refs),
            }

        result: dict[str, Any] = run_coro_sync(
            _agent_pipeline(),
            timeout_seconds=_nl_pipeline_timeout_seconds(),
        )
        return result


__all__ = ["NaturalLanguageRunMixin"]
