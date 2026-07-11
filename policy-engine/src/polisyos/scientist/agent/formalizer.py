"""Formalizer agents: draft -> canonical Trinity artifacts."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.canon import truncated_hash
from polisyos.ir.governance.policy_spec import InterventionSpec as TrinityInterventionSpec
from polisyos.ir.governance.policy_spec import ParameterSpec, PolicySpec
from polisyos.ir.governance.problem_frame import (
    ObjectiveSpec,
    ProblemDomain,
)
from polisyos.ir.governance.problem_frame import (
    ProblemFrame as TrinityProblemFrame,
)
from polisyos.ir.kernel.metrics import (
    ProductionMetricTaxonomy,
    build_production_metric_taxonomy,
    canonicalize_metric_id_with_diagnostics,
    taxonomy_diagnostic_note,
)
from polisyos.ir.model_layer.model_spec import (
    AgentConfig,
    AssumptionSpec,
    AssumptionType,
    EnvironmentConfig,
    ModelSpec,
)
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.agent._llm_timeouts import resolve_agent_llm_timeout_s
from polisyos.scientist.agent.prompts import get_formalizer_prompt
from polisyos.scientist.agent.protocols import DraftResult, FormalizerAgent
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.llm import TracedLLMClient

ZERO_ARTIFACT_REF = f"sha256:{'0' * 64}"
FINAL_POLICY_CLAIMS_SCHEMA_VERSION = "policyos.scientist.final_policy_claims.v1"
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_ARTIFACT_ID_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
logger = get_logger(__name__)
_SCHEMA_HEALING_MODE_ENV = "POLISYOS_FORMALIZER_SCHEMA_HEALING_MODE"
FINAL_POLICY_CLAIM_FAMILIES = frozenset(
    {
        "recommendation",
        "empirical",
        "numerical",
        "causal",
        "normative",
        "forecast",
        "distributional",
        "implementation",
        "caveat",
    }
)
_CLAIM_FAMILY_ALIASES = {
    "advice": "recommendation",
    "claim": "empirical",
    "compliance": "normative",
    "distribution": "distributional",
    "equity": "distributional",
    "evidence": "empirical",
    "factual": "empirical",
    "impact": "causal",
    "legal": "normative",
    "number": "numerical",
    "numeric": "numerical",
    "operational": "implementation",
    "policy_recommendation": "recommendation",
    "quantitative": "numerical",
    "risk": "caveat",
    "scenario": "forecast",
}

_MECHANISM_KIND_ALIASES = {
    "cash_grant": "tax_subsidy",
    "compensation": "tax_subsidy",
    "credit": "tax_subsidy",
    "credit_guarantee": "tax_subsidy",
    "custom_mechanism": "tax_subsidy",
    "direct_grant": "tax_subsidy",
    "digital_voucher": "tax_subsidy",
    "general_intervention": "tax_subsidy",
    "grant": "tax_subsidy",
    "loan_guarantee": "tax_subsidy",
    "matching_grant": "tax_subsidy",
    "microgrant": "tax_subsidy",
    "reimbursement": "tax_subsidy",
    "subsidy": "tax_subsidy",
    "tax_credit": "tax_subsidy",
    "tax_relief": "tax_subsidy",
    "voucher": "tax_subsidy",
    "wage_subsidy": "tax_subsidy",
    "working_capital_grant": "tax_subsidy",
}


def _resolve_formalizer_retries() -> int:
    raw = os.getenv("POLISYOS_FORMALIZER_LLM_RETRIES", "2")
    try:
        return max(0, int(raw.strip()))
    except ValueError:
        return 2


class FormalizerSchemaValidationError(ValueError):
    """Structured formalizer schema failure for strict production/debug gates."""

    def __init__(
        self,
        message: str,
        *,
        phase: str,
        field_errors: list[dict[str, Any]],
        draft_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.field_errors = [dict(item) for item in field_errors]
        self.failure = {
            "code": "llm_formalizer_schema_validation_failed",
            "layer": "llm_formalizer",
            "phase": phase,
            "message": message,
            "retryable": False,
            "next_action": (
                "Fix the formalizer prompt/output schema or disable strict schema mode "
                "only for exploratory local runs."
            ),
            "artifact_refs": {},
            "variant_failures": [],
            "field_errors": self.field_errors,
        }
        if draft_id:
            self.failure["draft_id"] = draft_id


def _resolve_schema_healing_mode(raw_mode: str | None) -> str:
    raw = raw_mode if raw_mode is not None else os.getenv(_SCHEMA_HEALING_MODE_ENV)
    mode = str(raw or "audit").strip().lower().replace("-", "_")
    if mode in {"strict", "fail", "failure", "error"}:
        return "strict"
    return "audit"


_RATE_PARAM_ALIASES = (
    "rate",
    "subsidy_rate",
    "tax_rate_reduction",
    "tax_relief_rate",
    "grant_rate",
    "coverage_rate",
    "reimbursement_rate",
    "guarantee_rate",
    "co_financing_rate",
    "cofinancing_rate",
)
_EXECUTABLE_PARAM_KEYS_BY_MECHANISM = {
    "adaptive_agent": frozenset(
        {
            "action_space",
            "learning_rate",
            "observation_space",
            "policy_model",
            "seed",
            "stochastic",
            "utility",
            "weights_artifact",
        }
    ),
    "income_tax": frozenset({"rate"}),
    "tax_subsidy": frozenset({"rate"}),
}
_EXECUTABLE_ADAPTIVE_AGENT_SLOTS = frozenset(
    {
        "agents.income",
        "agents.risk_aversion",
        "agents.skill_level",
    }
)
_ADAPTIVE_UTILITY_ALIASES = {
    "crra": "crra",
    "cara": "cara",
    "epstein_zin": "epstein_zin",
    "maximize_aid_efficiency": "crra",
    "maximize_msme_resilience": "crra",
    "maximize_survival_and_fairness": "crra",
}
_RELIEF_TERMS = frozenset(
    {
        "credit",
        "deduction",
        "exemption",
        "grant",
        "relief",
        "reduction",
        "subsidy",
        "support",
        "voucher",
    }
)
_TAX_COLLECTION_TERMS = frozenset({"collect", "collection", "levy", "raise_revenue"})
_DEFAULT_ADAPTIVE_OBSERVATION_SPACE = ["agents.income"]
_DEFAULT_ADAPTIVE_ACTIONS = ["no_support", "basic_support", "intensive_support"]
_DEFAULT_ADAPTIVE_AFFECTS = ["agents.income"]
_MODEL_INTERACTION_TOPOLOGY_ALIASES = {
    "complete": "random",
    "fully_mixed": "random",
    "mixed": "random",
    "well_mixed": "random",
    "grid": "lattice",
    "graph": "network",
    "networked": "network",
    "geo": "spatial",
    "geospatial": "spatial",
}
_MODEL_FIDELITY_LEVEL_ALIASES = {
    "fast": "surrogate_fluid",
    "low": "surrogate_fluid",
    "fluid": "surrogate_fluid",
    "discrete": "surrogate_discrete",
    "medium": "hybrid",
    "mid": "hybrid",
    "high": "full_discrete",
    "full": "full_discrete",
}


def _normalize_id(raw: str, *, prefix: str) -> str:
    value = re.sub(r"[^a-z0-9_]+", "_", raw.lower()).strip("_")
    value = re.sub(r"_+", "_", value)
    if not value:
        value = prefix
    if not value[0].isalpha():
        value = f"{prefix}_{value}"
    if _ID_RE.fullmatch(value):
        return value
    digest = truncated_hash(raw, length=10)
    return f"{prefix}_{digest}"


def _clean_text(value: Any, *, max_length: int = 4000) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:max_length]


def _first_text(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            text = _clean_text(value)
            if text:
                return text
    return ""


def _as_claim_refs(value: Any) -> list[str]:
    if isinstance(value, str):
        text = _clean_text(value, max_length=256)
        return [text] if text else []
    if not isinstance(value, list | tuple | set):
        return []
    refs: list[str] = []
    for item in value:
        text = _clean_text(item, max_length=256)
        if text and text not in refs:
            refs.append(text)
    return refs


def _claim_refs(payload: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    refs: list[str] = []
    grounding = payload.get("grounding")
    for key in keys:
        refs.extend(_as_claim_refs(payload.get(key)))
        if isinstance(grounding, dict):
            refs.extend(_as_claim_refs(grounding.get(key)))
    deduped: list[str] = []
    for ref in refs:
        if ref not in deduped:
            deduped.append(ref)
    return deduped


def _parse_major_claim_status(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"false", "0", "no", "minor", "non_major", "supporting"}:
            return False
        if normalized in {"true", "1", "yes", "major", "primary", "blocking"}:
            return True
    return bool(value)


def _classify_claim_family(text: str, payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    lowered = text.casefold()
    if any(key in payload for key in ("metric", "value", "numeric_value", "claim_value")):
        return "numerical"
    if re.search(r"(^|\s)[+-]?\d+(\.\d+)?\s*(%|percent|percentage points?|pp\b)", lowered):
        return "numerical"
    if any(
        token in lowered
        for token in (
            "authorized",
            "complies",
            "eligible",
            "legal",
            "norm",
            "required by",
            "statutory",
        )
    ):
        return "normative"
    if any(
        token in lowered
        for token in (
            "causes",
            "causal",
            "because of",
            "effect of",
            "impact of",
            "leads to",
            "treatment effect",
        )
    ):
        return "causal"
    if any(
        token in lowered
        for token in (
            "forecast",
            "expected to",
            "projected",
            "scenario",
            "will likely",
        )
    ):
        return "forecast"
    if any(
        token in lowered
        for token in (
            "distributional",
            "equity",
            "low-income",
            "regional",
            "subgroup",
            "vulnerable",
        )
    ):
        return "distributional"
    if any(
        token in lowered
        for token in (
            "dashboard",
            "implementation",
            "monitoring",
            "publish",
            "rollout",
        )
    ):
        return "implementation"
    if any(
        token in lowered
        for token in (
            "caveat",
            "limited",
            "residual risk",
            "uncertain",
            "uncertainty",
        )
    ):
        return "caveat"
    if any(
        token in lowered
        for token in (
            "observed",
            "evidence",
            "data show",
            "measured",
        )
    ):
        return "empirical"
    return "recommendation"


def _normalize_claim_family(
    raw_family: Any,
    *,
    text: str,
    payload: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    raw_text = _clean_text(raw_family, max_length=128)
    if not raw_text:
        return _classify_claim_family(text, payload), None
    normalized = _normalize_id(raw_text, prefix="claim_family")
    family = _CLAIM_FAMILY_ALIASES.get(normalized, normalized)
    if family in FINAL_POLICY_CLAIM_FAMILIES:
        return family, None
    inferred = _classify_claim_family(text, payload)
    return inferred, {
        "code": "unsupported_claim_family_normalized",
        "severity": "warn",
        "raw_claim_family": raw_text,
        "normalized_claim_family": inferred,
        "message": (
            f"Unsupported claim family {raw_text!r} was normalized to {inferred!r}."
        ),
    }


def _claim_grounding(payload: dict[str, Any]) -> dict[str, Any]:
    grounding = payload.get("grounding")
    if not isinstance(grounding, dict):
        grounding = {}
    rationale = _first_text(
        {**grounding, **payload},
        (
            "no_grounding_rationale",
            "grounding_rationale",
            "not_grounded_rationale",
        ),
    )
    return {
        "data_refs": _claim_refs(
            payload,
            (
                "data_refs",
                "data_source_refs",
                "source_refs",
                "fabric_refs",
                "data_snapshot_refs",
            ),
        ),
        "method_refs": _claim_refs(
            payload,
            ("method_refs", "foundry_method_refs", "analysis_refs"),
        ),
        "norm_refs": _claim_refs(
            payload,
            ("norm_refs", "normative_refs", "norm_ids", "legal_refs"),
        ),
        "no_grounding_rationale": rationale or None,
    }


def _copy_claim_field(
    claim: dict[str, Any],
    payload: dict[str, Any],
    *,
    source_key: str,
    target_key: str | None = None,
) -> None:
    if source_key in payload and payload[source_key] is not None:
        claim[target_key or source_key] = payload[source_key]


def _normalize_final_policy_claim(
    payload: dict[str, Any],
    *,
    index: int,
    source: str,
    default_major: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    text = _first_text(
        payload,
        ("text", "claim", "statement", "summary", "description", "rationale"),
    )
    if not text:
        return None, [
            {
                "code": "policy_claim_text_missing",
                "severity": "warn",
                "source": source,
                "message": "A candidate policy claim was skipped because it had no text.",
            }
        ]

    family, family_issue = _normalize_claim_family(
        payload.get("claim_family")
        or payload.get("family")
        or payload.get("claim_type")
        or payload.get("type"),
        text=text,
        payload=payload,
    )
    if family_issue is not None:
        issues.append({**family_issue, "source": source})

    raw_claim_id = _clean_text(
        payload.get("claim_id")
        or payload.get("id")
        or f"{source}_{index + 1}_{truncated_hash(text, length=8)}",
        max_length=128,
    )
    claim_id = _normalize_id(raw_claim_id, prefix="claim")
    major = _parse_major_claim_status(
        payload.get("major")
        if "major" in payload
        else payload.get("importance") or payload.get("status"),
        default=default_major,
    )
    grounding = _claim_grounding(payload)
    claim: dict[str, Any] = {
        "claim_id": claim_id,
        "claim_family": family,
        "claim_type": family,
        "major": major,
        "text": text,
        "source": source,
        "grounding": grounding,
    }
    for key in ("data_refs", "method_refs", "norm_refs"):
        if grounding[key]:
            claim[key] = list(grounding[key])
    if grounding["no_grounding_rationale"]:
        claim["no_grounding_rationale"] = grounding["no_grounding_rationale"]

    for key in (
        "policy_action",
        "action",
        "intervention",
        "intervention_id",
        "metric",
        "value",
        "numeric_value",
        "claim_value",
        "tolerance",
        "unit",
        "direction",
        "confidence",
        "extraction_confidence",
    ):
        _copy_claim_field(claim, payload, source_key=key)
    return claim, issues


def _model_dump_or_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return dict(value)
    return dict(vars(value))


def _intervention_claim_payloads(
    draft: DraftResult,
    trinity_bundle: TrinityBundle | None,
) -> list[dict[str, Any]]:
    raw_items: list[Any] = []
    if draft.interventions:
        raw_items.extend(draft.interventions)
    elif trinity_bundle is not None:
        raw_items.extend(list(getattr(trinity_bundle.policy_spec, "interventions", []) or []))

    payloads: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_items):
        try:
            item = _model_dump_or_dict(raw_item)
        except (TypeError, ValueError):
            continue
        intervention_id = _clean_text(
            item.get("intervention_id") or item.get("name") or f"intervention_{index + 1}",
            max_length=128,
        )
        kind = _clean_text(item.get("kind") or item.get("mechanism_type") or "policy_action")
        description = _first_text(item, ("description", "summary", "rationale"))
        action_text = description or f"Implement {kind.replace('_', ' ')} for {intervention_id}."
        payloads.append(
            {
                "claim_id": f"rec_{intervention_id}",
                "claim_family": "recommendation",
                "major": True,
                "text": action_text,
                "policy_action": description or kind,
                "intervention_id": intervention_id,
            }
        )
    return payloads


def _narrative_fallback_claim_payload(draft: DraftResult) -> dict[str, Any] | None:
    text = _clean_text(draft.narrative)
    if not text:
        return None
    sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    return {
        "claim_id": f"rec_{draft.draft_id}",
        "claim_family": "recommendation",
        "major": True,
        "text": sentence,
        "no_grounding_rationale": (
            "Generated from draft narrative because no explicit claim supports or "
            "intervention claims were available; human review required."
        ),
    }


def _dedupe_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, bool]] = set()
    for claim in claims:
        signature = (
            str(claim.get("claim_family") or ""),
            _clean_text(claim.get("text")).casefold(),
            bool(claim.get("major")),
        )
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(claim)
    return deduped


def build_final_policy_claims_report(
    *,
    draft: DraftResult,
    trinity_bundle: TrinityBundle | None = None,
) -> dict[str, Any]:
    """Extract a machine-readable final-claims sidecar from a policy draft."""
    issues: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []

    raw_supports = draft.claim_supports if isinstance(draft.claim_supports, list) else []
    for index, raw_support in enumerate(raw_supports):
        if not isinstance(raw_support, dict):
            issues.append(
                {
                    "code": "policy_claim_support_unreadable",
                    "severity": "warn",
                    "message": "A non-object claim support entry was skipped.",
                    "source": "draft_claim_support",
                }
            )
            continue
        claim, claim_issues = _normalize_final_policy_claim(
            raw_support,
            index=index,
            source="draft_claim_support",
            default_major=True,
        )
        issues.extend(claim_issues)
        if claim is not None:
            claims.append(claim)

    if not any(bool(claim.get("major")) for claim in claims):
        for index, payload in enumerate(_intervention_claim_payloads(draft, trinity_bundle)):
            claim, claim_issues = _normalize_final_policy_claim(
                payload,
                index=index,
                source="trinity_policy_spec",
                default_major=True,
            )
            issues.extend(claim_issues)
            if claim is not None:
                claims.append(claim)

    human_review_required = False
    if not claims:
        fallback_payload = _narrative_fallback_claim_payload(draft)
        if fallback_payload is not None:
            human_review_required = True
            claim, claim_issues = _normalize_final_policy_claim(
                fallback_payload,
                index=0,
                source="draft_narrative_fallback",
                default_major=True,
            )
            issues.extend(claim_issues)
            if claim is not None:
                claims.append(claim)
            issues.append(
                {
                    "code": "policy_claim_extraction_ambiguous",
                    "severity": "warn",
                    "message": (
                        "Final policy claims were inferred from narrative text and "
                        "require human review."
                    ),
                    "source": "draft_narrative_fallback",
                }
            )

    claims = _dedupe_claims(claims)
    major_claims = [claim for claim in claims if bool(claim.get("major"))]
    if not claims:
        issues.append(
            {
                "code": "policy_claim_extraction_failed",
                "severity": "fail",
                "message": "No machine-readable final policy claims could be extracted.",
                "source": "formalizer",
            }
        )
    elif not major_claims:
        issues.append(
            {
                "code": "no_major_policy_claims",
                "severity": "fail",
                "message": "Final policy artifact has no machine-readable major claims.",
                "source": "formalizer",
            }
        )

    if any(issue.get("severity") == "fail" for issue in issues):
        extraction_status = "fail"
    elif human_review_required or any(
        issue.get("code") == "policy_claim_extraction_ambiguous" for issue in issues
    ):
        extraction_status = "review_required"
        human_review_required = True
    else:
        extraction_status = "pass"

    families: dict[str, int] = {}
    for claim in claims:
        family = str(claim.get("claim_family") or "unknown")
        families[family] = families.get(family, 0) + 1

    return {
        "schema_version": FINAL_POLICY_CLAIMS_SCHEMA_VERSION,
        "extraction_status": extraction_status,
        "human_review_required": human_review_required,
        "draft_id": draft.draft_id,
        "problem_frame_ref": draft.problem_frame_ref,
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "human_artifact": {
            "kind": "scientist.policy_draft",
            "draft_id": draft.draft_id,
            "narrative": draft.narrative,
            "rationale": draft.rationale,
        },
        "claims": claims,
        "major_claims": major_claims,
        "issues": issues,
        "summary": {
            "claim_count": len(claims),
            "major_claim_count": len(major_claims),
            "claim_families": families,
        },
    }


def _normalize_mechanism_kind(raw: str) -> str:
    kind = _normalize_id(raw, prefix="mechanism")
    return _MECHANISM_KIND_ALIASES.get(kind, kind)


def _intervention_semantic_text(intervention: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("intervention_id", "kind", "description"):
        value = intervention.get(key)
        if value is not None:
            parts.append(str(value))
    notes = intervention.get("notes")
    if isinstance(notes, list):
        parts.extend(str(item) for item in notes)
    params = intervention.get("params")
    if isinstance(params, dict):
        parts.extend(str(key) for key in params.keys())
        parts.extend(str(value) for value in params.values() if isinstance(value, str))
    return " ".join(parts).lower().replace("-", "_").replace(" ", "_")


def _normalize_mechanism_kind_for_intervention(
    kind: str,
    intervention: dict[str, Any],
) -> str:
    if kind != "income_tax":
        return kind
    semantic_text = _intervention_semantic_text(intervention)
    if any(term in semantic_text for term in _TAX_COLLECTION_TERMS):
        return kind
    if any(term in semantic_text for term in _RELIEF_TERMS):
        return "tax_subsidy"
    return kind


def _unique_id(base: str, used: set[str], *, prefix: str, discriminator: str) -> str:
    """Return a Trinity-safe identifier that is unique within the current artifact."""
    candidate = base
    suffix = 1
    while candidate in used:
        suffix += 1
        digest = truncated_hash(f"{discriminator}:{suffix}", length=6)
        candidate = _normalize_id(f"{base}_{suffix}_{digest}", prefix=prefix)
    used.add(candidate)
    return candidate


def _infer_domain(text: str) -> ProblemDomain:
    lowered = text.lower()
    if any(token in lowered for token in {"tax", "income", "poverty", "gdp", "budget"}):
        return ProblemDomain.FISCAL
    if any(token in lowered for token in {"health", "hospital", "medical"}):
        return ProblemDomain.HEALTHCARE
    if any(token in lowered for token in {"school", "education", "student"}):
        return ProblemDomain.EDUCATION
    return ProblemDomain.CUSTOM


def _default_target() -> dict[str, Any]:
    return {
        "kind": "predicate",
        "field": "id",
        "operator": "==",
        "value": "all",
    }


def _default_schedule() -> dict[str, Any]:
    return {"start_step": 0, "duration_steps": 12}


def _canonicalize_param_value(value: Any) -> Any:
    """Convert generated fallback params to Trinity-safe canonical values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return format(Decimal(str(value)), "f")
    if isinstance(value, dict):
        return {str(key): _canonicalize_param_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize_param_value(item) for item in value]
    return value


def _canonicalize_params(params: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _canonicalize_param_value(value) for key, value in params.items()}


def _plain_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _coerce_rate(value: Any) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        multiplier = Decimal("1")
        if text.endswith("%"):
            text = text[:-1].strip()
            multiplier = Decimal("0.01")
        try:
            rate = Decimal(text) * multiplier
        except InvalidOperation:
            return None
    elif isinstance(value, Decimal):
        rate = value
    elif isinstance(value, int):
        rate = Decimal(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            return None
        rate = Decimal(str(value))
    else:
        return None

    if rate < Decimal("0") or rate > Decimal("1"):
        return None
    return _plain_decimal(rate)


def _normalize_agent_slots(value: Any) -> list[str]:
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if not isinstance(item, str):
            continue
        slot_id = item.strip()
        if (
            not slot_id.startswith("agents.")
            or slot_id not in _EXECUTABLE_ADAPTIVE_AGENT_SLOTS
            or slot_id in seen
        ):
            continue
        normalized.append(slot_id)
        seen.add(slot_id)
    return normalized


def _normalize_adaptive_action_space(action_space: Any) -> dict[str, Any]:
    if not isinstance(action_space, dict):
        action_space = {}
    normalized = dict(action_space)

    action_type = normalized.get("type")
    if action_type not in {"continuous", "discrete"}:
        action_type = "discrete"
    normalized["type"] = action_type

    affects = _normalize_agent_slots(normalized.get("affects"))
    normalized["affects"] = affects or list(_DEFAULT_ADAPTIVE_AFFECTS)

    if action_type == "discrete":
        actions = normalized.get("actions")
        if not isinstance(actions, list) or not actions:
            actions = list(_DEFAULT_ADAPTIVE_ACTIONS)
        normalized["actions"] = actions
        normalized.setdefault("n_categories", len(actions))
    elif "dim" not in normalized:
        normalized["dim"] = len(normalized["affects"])

    return normalized


def _normalize_adaptive_utility(value: Any) -> str:
    if not isinstance(value, str):
        return "crra"
    normalized = _normalize_id(value, prefix="utility")
    return _ADAPTIVE_UTILITY_ALIASES.get(normalized, "crra")


def _enum_alias_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _schema_healing_event(path: str, raw: object, normalized: str) -> dict[str, Any]:
    return {
        "path": path,
        "raw": raw,
        "normalized": normalized,
        "note": f"schema_healed:{path}:{raw}->{normalized}",
    }


def _normalize_model_spec_aliases_for_validation(data: object) -> list[dict[str, Any]]:
    healing_events: list[dict[str, Any]] = []
    if not isinstance(data, dict):
        return healing_events
    model_spec = data.get("model_spec")
    if not isinstance(model_spec, dict):
        return healing_events

    notes = [str(note) for note in model_spec.get("notes") or [] if str(note).strip()]

    def _append_healing(path: str, raw: object, normalized: str) -> None:
        event = _schema_healing_event(path, raw, normalized)
        note = str(event["note"])
        healing_events.append(event)
        if note not in notes and len(notes) < 50:
            notes.append(note)

    agent_config = model_spec.get("agent_config")
    if isinstance(agent_config, dict):
        raw_topology = agent_config.get("interaction_topology")
        topology_key = _enum_alias_key(raw_topology)
        normalized_topology = _MODEL_INTERACTION_TOPOLOGY_ALIASES.get(topology_key)
        if normalized_topology is not None:
            agent_config["interaction_topology"] = normalized_topology
            _append_healing(
                "model_spec.agent_config.interaction_topology",
                raw_topology,
                normalized_topology,
            )

    raw_fidelity = model_spec.get("fidelity_level")
    fidelity_key = _enum_alias_key(raw_fidelity)
    normalized_fidelity = _MODEL_FIDELITY_LEVEL_ALIASES.get(fidelity_key)
    if normalized_fidelity is not None:
        model_spec["fidelity_level"] = normalized_fidelity
        _append_healing("model_spec.fidelity_level", raw_fidelity, normalized_fidelity)

    model_spec["notes"] = notes
    return healing_events


def _normalize_problem_frame_metric_aliases_for_validation(
    data: object,
    *,
    taxonomy: ProductionMetricTaxonomy | None = None,
    fail_unknown: bool = False,
) -> list[dict[str, Any]]:
    healing_events: list[dict[str, Any]] = []
    if not isinstance(data, dict):
        return healing_events
    problem_frame = data.get("problem_frame")
    if not isinstance(problem_frame, dict):
        return healing_events
    active_taxonomy = taxonomy or build_production_metric_taxonomy()

    notes = [str(note) for note in problem_frame.get("notes") or [] if str(note).strip()]

    def _append_diagnostics(diagnostics: list[dict[str, Any]]) -> None:
        healing_events.extend(diagnostics)
        for diagnostic in diagnostics:
            note = taxonomy_diagnostic_note(diagnostic)
            if note not in notes and len(notes) < 50:
                notes.append(note)
            # Preserve existing schema-healing telemetry consumers while adding
            # metric-taxonomy diagnostics.
            schema_note = (
                "schema_healed:"
                f"{diagnostic.get('path')}:{diagnostic.get('raw')}"
                f"->{diagnostic.get('normalized')}"
            )
            if schema_note not in notes and len(notes) < 50:
                notes.append(schema_note)

    def _append_healing(path: str, raw: object, normalized: str) -> None:
        event = _schema_healing_event(path, raw, normalized)
        note = str(event["note"])
        healing_events.append(event)
        if note not in notes and len(notes) < 50:
            notes.append(note)

    for collection_name in ("objectives", "kpis"):
        collection = problem_frame.get(collection_name)
        if not isinstance(collection, list):
            continue
        for index, item in enumerate(collection):
            if not isinstance(item, dict):
                continue
            raw_metric_id = item.get("metric_id")
            if not isinstance(raw_metric_id, str) or not raw_metric_id.strip():
                continue
            result = canonicalize_metric_id_with_diagnostics(
                raw_metric_id,
                taxonomy=active_taxonomy,
                path=f"problem_frame.{collection_name}[{index}].metric_id",
                fail_unknown=fail_unknown,
            )
            normalized_metric_id = result.metric_id
            if normalized_metric_id != raw_metric_id:
                item["metric_id"] = normalized_metric_id
                _append_diagnostics(result.diagnostics)

    problem_frame["notes"] = notes
    return healing_events


def _normalize_mechanism_params(kind: str, params: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(params)
    if kind in {"income_tax", "tax_subsidy"} and "rate" not in normalized:
        for alias in _RATE_PARAM_ALIASES:
            if alias not in normalized:
                continue
            rate = _coerce_rate(normalized[alias])
            if rate is not None:
                normalized["rate"] = rate
                break
        else:
            normalized["rate"] = "0.1"

    executable_keys = _EXECUTABLE_PARAM_KEYS_BY_MECHANISM.get(kind)
    if executable_keys is not None:
        normalized = {key: value for key, value in normalized.items() if key in executable_keys}

    if kind == "adaptive_agent":
        observation_space = normalized.get("observation_space")
        observation_slots = _normalize_agent_slots(observation_space)
        normalized["observation_space"] = observation_slots or list(
            _DEFAULT_ADAPTIVE_OBSERVATION_SPACE
        )
        normalized["action_space"] = _normalize_adaptive_action_space(
            normalized.get("action_space")
        )
        normalized["utility"] = _normalize_adaptive_utility(normalized.get("utility"))

    return normalized


def _normalize_parameter_path(raw_path: Any) -> str:
    path = str(raw_path or "").strip()
    while path.startswith("params."):
        path = path.removeprefix("params.")
    return path


def _resolve_parameter_path(params: dict[str, Any], path: str) -> tuple[bool, Any]:
    if not path:
        return False, None
    current: Any = params
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _is_numeric_tunable_value(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, int | Decimal):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        if text.endswith("%"):
            text = text[:-1].strip()
        try:
            Decimal(text)
        except InvalidOperation:
            return False
        return True
    if isinstance(value, dict) and value.get("_type") == "decimal":
        return _is_numeric_tunable_value(value.get("value"))
    return False


def _append_policy_note(policy_data: dict[str, Any], note: str) -> None:
    notes = list(policy_data.get("notes") or [])
    if note not in notes and len(notes) < 50:
        notes.append(note)
    policy_data["notes"] = notes


def _normalize_parameter_specs(
    policy_data: dict[str, Any],
    interventions: list[Any],
) -> None:
    interventions_by_id: dict[str, dict[str, Any]] = {}
    for intervention in interventions:
        if isinstance(intervention, dict) and isinstance(intervention.get("params"), dict):
            interventions_by_id[str(intervention.get("intervention_id") or "")] = intervention

    normalized_specs: list[dict[str, Any]] = []
    for raw_spec in list(policy_data.get("parameters") or []):
        if not isinstance(raw_spec, dict):
            continue
        spec = dict(raw_spec)
        param_id = str(spec.get("param_id") or "parameter")
        intervention_id = str(spec.get("intervention_id") or "")
        intervention = interventions_by_id.get(intervention_id)
        raw_path = spec.get("param_path")
        path = _normalize_parameter_path(raw_path)
        if intervention is None:
            _append_policy_note(
                policy_data,
                f"dropped_unresolved_parameter_spec:{param_id}:{raw_path}",
            )
            continue
        resolved, value = _resolve_parameter_path(intervention["params"], path)
        if not resolved:
            _append_policy_note(
                policy_data,
                f"dropped_unresolved_parameter_spec:{param_id}:{raw_path}",
            )
            continue
        if not _is_numeric_tunable_value(value):
            _append_policy_note(
                policy_data,
                f"dropped_non_numeric_parameter_spec:{param_id}:{path}",
            )
            continue
        spec["param_path"] = path
        spec["default_value"] = _canonicalize_param_value(value)
        normalized_specs.append(spec)

    policy_data["parameters"] = normalized_specs


def _is_valid_artifact_ref(value: Any) -> bool:
    return isinstance(value, str) and bool(_ARTIFACT_ID_RE.fullmatch(value.strip()))


def _intervention_rate(intervention: dict[str, Any]) -> Decimal | None:
    params = intervention.get("params")
    if not isinstance(params, dict):
        return None
    rate = _coerce_rate(params.get("rate"))
    if rate is None:
        return None
    try:
        return Decimal(rate)
    except InvalidOperation:
        return None


def _needs_budget_feasibility_constraint(interventions: list[Any]) -> bool:
    support_like_count = 0
    for intervention in interventions:
        if not isinstance(intervention, dict):
            continue
        kind = str(intervention.get("kind") or "")
        if kind in {"tax_subsidy", "income_tax"}:
            support_like_count += 1
        rate = _intervention_rate(intervention)
        if kind == "tax_subsidy" and rate is not None and rate >= Decimal("0.5"):
            return True
    return support_like_count >= 2


def _ensure_budget_feasibility_constraint(bundle_data: dict[str, Any]) -> None:
    policy_data = bundle_data.get("policy_spec") or {}
    interventions = policy_data.get("interventions") or []
    if not _needs_budget_feasibility_constraint(interventions):
        return

    problem_data = bundle_data.get("problem_frame") or {}
    soft_constraints = list(problem_data.get("soft_constraints") or [])
    if any(
        isinstance(item, dict) and item.get("constraint_id") == "wartime_budget_feasibility"
        for item in soft_constraints
    ):
        return
    soft_constraints.append(
        {
            "constraint_id": "wartime_budget_feasibility",
            "constraint_type": "soft",
            "value": "fiscally_bounded_targeting_required",
            "penalty_weight": "1",
            "notes": [
                "Auto-added because high-rate or overlapping support interventions "
                "require budget feasibility review."
            ],
        }
    )
    problem_data["soft_constraints"] = soft_constraints
    bundle_data["problem_frame"] = problem_data


def _normalize_trinity_bundle_for_linker(bundle: TrinityBundle) -> TrinityBundle:
    bundle_data = bundle.model_dump(mode="python")
    policy_data = bundle_data.get("policy_spec") or {}
    interventions = policy_data.get("interventions") or []
    for intervention in interventions:
        if not isinstance(intervention, dict):
            continue
        kind = _normalize_mechanism_kind(str(intervention.get("kind") or "tax_subsidy"))
        kind = _normalize_mechanism_kind_for_intervention(kind, intervention)
        params = intervention.get("params")
        if not isinstance(params, dict):
            params = {}
        params = _canonicalize_params(params)
        intervention["kind"] = kind
        normalized_params = _normalize_mechanism_params(kind, params)
        if (
            kind == "adaptive_agent"
            and "weights_artifact" in normalized_params
            and not _is_valid_artifact_ref(normalized_params.get("weights_artifact"))
        ):
            normalized_params.pop("weights_artifact", None)
            _append_policy_note(
                policy_data,
                "dropped_invalid_runtime_artifact_ref:"
                f"{intervention.get('intervention_id')}:weights_artifact",
            )
        intervention["params"] = normalized_params
    _normalize_parameter_specs(policy_data, interventions)
    _ensure_budget_feasibility_constraint(bundle_data)
    return TrinityBundle.model_validate(bundle_data)


def _recorded_call_value(call: object, field: str) -> object | None:
    if isinstance(call, Mapping):
        return call.get(field)
    return getattr(call, field, None)


def trinity_bundle_formalizer_generator_path(
    bundle: TrinityBundle,
    *,
    recorded_calls: Sequence[object],
) -> Literal["model_generated", "degraded_mock_fallback", "path_unrecorded"]:
    """Derive formalizer provenance from the actual recorded response window.

    A returned bundle is model-generated only when a successful formalizer call
    in the supplied window contains Trinity JSON that normalizes to that exact
    bundle. Readable but non-matching Trinity evidence is degraded; an empty or
    unusable window leaves provenance explicitly unrecorded.
    """

    expected = _normalize_trinity_bundle_for_linker(bundle).model_dump(mode="json")
    readable_response_seen = False
    for call in recorded_calls:
        if _recorded_call_value(call, "role_hint") != "formalizer":
            continue
        if _recorded_call_value(call, "status") != "success":
            continue
        parsed = _recorded_call_value(call, "parsed_json")
        if not isinstance(parsed, Mapping):
            continue
        candidate_data = deepcopy(dict(parsed))
        try:
            _normalize_problem_frame_metric_aliases_for_validation(
                candidate_data,
                taxonomy=build_production_metric_taxonomy(),
                fail_unknown=False,
            )
            _normalize_model_spec_aliases_for_validation(candidate_data)
            candidate = TrinityBundle.model_validate(candidate_data)
        except (ValidationError, ValueError, TypeError):
            continue
        if candidate.schema_version != bundle.schema_version:
            candidate = candidate.model_copy(
                update={"schema_version": bundle.schema_version}
            )
        candidate = _normalize_trinity_bundle_for_linker(candidate)
        readable_response_seen = True
        if candidate.model_dump(mode="json") == expected:
            return "model_generated"
    if readable_response_seen:
        return "degraded_mock_fallback"
    return "path_unrecorded"


def _draft_interventions_to_policy_spec(
    draft: DraftResult,
    *,
    policy_id: str,
    schema_version: str,
) -> PolicySpec:
    interventions: list[TrinityInterventionSpec] = []
    params_specs: list[ParameterSpec] = []
    used_intervention_ids: set[str] = set()

    if draft.interventions:
        raw_items = draft.interventions
    else:
        raw_items = [
            {
                "kind": "tax_subsidy",
                "target": _default_target(),
                "schedule": _default_schedule(),
                "params": {"rate": "0.1"},
            }
        ]

    for idx, raw_item in enumerate(raw_items):
        item = dict(raw_item)
        raw_intervention_id = str(
            item.get("intervention_id") or item.get("name") or f"intervention_{idx + 1}"
        )
        intervention_id = _unique_id(
            _normalize_id(raw_intervention_id, prefix="intervention"),
            used_intervention_ids,
            prefix="intervention",
            discriminator=f"{idx}:{raw_intervention_id}:{item.get('description', '')}",
        )
        kind = _normalize_mechanism_kind(
            str(item.get("kind") or item.get("mechanism_type") or "tax_subsidy")
        )
        item_for_kind = dict(item)
        item_for_kind["intervention_id"] = intervention_id
        kind = _normalize_mechanism_kind_for_intervention(kind, item_for_kind)
        params = item.get("params") or item.get("parameters") or {"rate": "0.1"}
        if not isinstance(params, dict):
            params = {"value": str(params)}
        params = _canonicalize_params(params)
        params = _normalize_mechanism_params(kind, params)

        intervention = TrinityInterventionSpec.model_validate(
            {
                "intervention_id": intervention_id,
                "kind": kind,
                "target": item.get("target") or _default_target(),
                "schedule": item.get("schedule") or _default_schedule(),
                "params": params,
                "notes": (
                    [str(item.get("description", "")).strip()] if item.get("description") else []
                ),
            }
        )
        interventions.append(intervention)

        for param_key, param_value in intervention.params.items():
            param_id = _normalize_id(f"{intervention_id}_{param_key}", prefix="param")
            params_specs.append(
                ParameterSpec(
                    param_id=param_id,
                    intervention_id=intervention_id,
                    param_path=str(param_key),
                    default_value=param_value,
                )
            )

    return PolicySpec(
        schema_version=schema_version,
        policy_id=policy_id,
        interventions=interventions,
        parameters=params_specs,
        labels=["scientist", "trinity"],
        description=draft.rationale or None,
    )


def _build_trinity_bundle_from_draft(draft: DraftResult, *, schema_version: str) -> TrinityBundle:
    digest = truncated_hash(draft.draft_id, length=10)
    problem_id = _normalize_id(draft.problem_frame_ref or f"problem_{digest}", prefix="problem")
    policy_id = _normalize_id(f"policy_{digest}", prefix="policy")
    model_id = _normalize_id(f"model_{digest}", prefix="model")

    objectives = [
        ObjectiveSpec(
            objective_id="objective_primary",
            metric_id="avg_income",
            direction="maximize",
        )
    ]

    problem_frame = TrinityProblemFrame(
        schema_version=schema_version,
        problem_id=problem_id,
        domain=_infer_domain(draft.narrative),
        objectives=objectives,
        hard_constraints=[],
        soft_constraints=[],
        narrative=draft.narrative,
        labels=["scientist", "trinity"],
    )

    policy_spec = _draft_interventions_to_policy_spec(
        draft,
        policy_id=policy_id,
        schema_version=schema_version,
    )

    assumptions: list[AssumptionSpec] = []
    if draft.rationale:
        assumptions.append(
            AssumptionSpec(
                assumption_id="assumption_rationale",
                assumption_type=AssumptionType.STRUCTURAL,
                description=draft.rationale[:500],
            )
        )

    model_spec = ModelSpec(
        schema_version=schema_version,
        model_id=model_id,
        data_snapshot_ref=ZERO_ARTIFACT_REF,
        agent_config=AgentConfig(total_agents=1000, max_agents=1000),
        assumptions=assumptions,
        environment_config=EnvironmentConfig(random_seed=42, stochastic=True),
        labels=["scientist", "trinity"],
    )

    bundle = TrinityBundle(
        schema_version=schema_version,
        problem_frame=problem_frame,
        policy_spec=policy_spec,
        model_spec=model_spec,
    )
    return _normalize_trinity_bundle_for_linker(bundle)


def _to_trinity(ir: Any, *, schema_version: str = "1.0") -> TrinityBundle:
    if isinstance(ir, TrinityBundle):
        if ir.schema_version == schema_version:
            return ir
        return ir.model_copy(update={"schema_version": schema_version})

    raise TypeError(f"Unsupported IR type for Trinity conversion: {type(ir)}")


class MockFormalizerAgent:
    """Mock implementation of FormalizerAgent for tests and fallback paths."""

    def __init__(self) -> None:
        self._formalization_count: int = 0
        self._repair_count: int = 0

    async def formalize(
        self,
        draft: DraftResult,
        *,
        schema_version: str = "1.0",
    ) -> TrinityBundle:
        if not draft.draft_id:
            raise ValueError("Draft must have a valid draft_id")

        self._formalization_count += 1
        return _build_trinity_bundle_from_draft(draft, schema_version=schema_version)

    async def repair_ir(
        self,
        ir: TrinityBundle,
        errors: list[str],
        *,
        hint: str | None = None,
    ) -> TrinityBundle:
        self._repair_count += 1

        bundle = _to_trinity(ir)
        bundle_data = bundle.model_dump(mode="python")

        lowered_errors = " ".join(error.lower() for error in errors)
        if "intervention" in lowered_errors and not bundle_data["policy_spec"]["interventions"]:
            bundle_data["policy_spec"]["interventions"] = [
                {
                    "intervention_id": "intervention_repair",
                    "kind": "tax_subsidy",
                    "target": _default_target(),
                    "schedule": _default_schedule(),
                    "params": {"rate": "0.1"},
                }
            ]
        if "data_snapshot_ref" in lowered_errors or not bundle_data["model_spec"].get(
            "data_snapshot_ref"
        ):
            bundle_data["model_spec"]["data_snapshot_ref"] = ZERO_ARTIFACT_REF
        if hint:
            notes = list(bundle_data["policy_spec"].get("notes") or [])
            notes.append(f"repair_hint: {hint}")
            bundle_data["policy_spec"]["notes"] = notes

        repaired = _normalize_trinity_bundle_for_linker(TrinityBundle.model_validate(bundle_data))
        return repaired

    async def validate_structure(
        self,
        ir: TrinityBundle,
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []

        try:
            bundle = _to_trinity(ir)
            if not bundle.problem_frame.problem_id:
                errors.append("Missing problem_frame.problem_id")
            if not bundle.policy_spec.interventions:
                errors.append("No interventions defined")
            if not bundle.model_spec.data_snapshot_ref:
                errors.append("Missing model_spec.data_snapshot_ref")
        except (AttributeError, TypeError, ValidationError, ValueError) as exc:
            envelope = emit_degraded_path(
                component="agent.formalizer",
                operation="validate_structure",
                reason="structure_validation_failed",
                exc=exc,
                log=logger,
            )
            errors.append(f"Validation error: {envelope['message']}")

        return len(errors) == 0, errors

    @property
    def formalization_count(self) -> int:
        return self._formalization_count

    @property
    def repair_count(self) -> int:
        return self._repair_count

    def reset(self) -> None:
        self._formalization_count = 0
        self._repair_count = 0


class LLMFormalizerAgent:
    """LLM-powered Formalizer; Trinity-first."""

    MAX_RETRIES = _resolve_formalizer_retries()

    def __init__(
        self,
        llm_client: Any,
        model_name: str | None = None,
        *,
        method_catalog_snapshot: dict[str, Any] | None = None,
        enable_response_healing: bool = False,
        schema_healing_mode: str | None = None,
        metric_taxonomy: ProductionMetricTaxonomy | None = None,
        fail_unknown_metrics: bool = False,
    ) -> None:
        if llm_client is not None and not isinstance(llm_client, TracedLLMClient):
            self._llm = TracedLLMClient(llm_client, model_name=model_name)
        else:
            self._llm = llm_client
        self._fallback = MockFormalizerAgent()
        self._method_catalog_snapshot = dict(method_catalog_snapshot or {})
        self._enable_response_healing = bool(enable_response_healing)
        self._schema_healing_mode = _resolve_schema_healing_mode(schema_healing_mode)
        self._metric_taxonomy = metric_taxonomy or build_production_metric_taxonomy()
        self._fail_unknown_metrics = bool(fail_unknown_metrics)
        self._timeout_s = resolve_agent_llm_timeout_s(
            "POLISYOS_FORMALIZER_LLM_TIMEOUT_S",
            default=60.0,
        )

    def set_method_catalog_snapshot(self, payload: dict[str, Any] | None) -> None:
        self._method_catalog_snapshot = dict(payload or {})

    async def formalize(
        self,
        draft: DraftResult,
        *,
        schema_version: str = "1.0",
    ) -> TrinityBundle:
        prompt = get_formalizer_prompt(method_catalog_snapshot=self._method_catalog_snapshot)

        user_message = f"""
DRAFT TO FORMALIZE:
{draft.narrative}

PROPOSED INTERVENTIONS:
{json.dumps(draft.interventions, indent=2)}

RATIONALE:
{draft.rationale}

Generate a valid TrinityBundle v{schema_version} JSON.
"""

        last_error: str | None = None
        last_schema_error: str | None = None
        for attempt in range(self.MAX_RETRIES + 1):
            attempt_message = user_message
            if last_error and attempt > 0:
                attempt_message += (
                    f"\n\nPREVIOUS ERROR (attempt {attempt}):\n{last_error}\n"
                    "Please fix and try again."
                )

            try:
                response = await asyncio.wait_for(
                    self._llm.generate(
                        system=prompt,
                        user=attempt_message,
                        response_format={"type": "json_object"},
                        plugins=(
                            [{"id": "response-healing"}] if self._enable_response_healing else None
                        ),
                        timeout=self._timeout_s,
                    ),
                    timeout=self._timeout_s + 5.0,
                )
            except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
                envelope = emit_degraded_path(
                    component="agent.formalizer",
                    operation="formalize",
                    reason="llm_call_failed",
                    exc=exc,
                    details={"attempt": attempt + 1, "draft_id": draft.draft_id},
                    log=logger,
                )
                last_error = f"LLM call failed: {envelope['message']}"
                continue

            content = response.content if hasattr(response, "content") else str(response)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            try:
                data = json.loads(content)
                schema_healing_events = [
                    *_normalize_problem_frame_metric_aliases_for_validation(
                        data,
                        taxonomy=self._metric_taxonomy,
                        fail_unknown=self._fail_unknown_metrics,
                    ),
                    *_normalize_model_spec_aliases_for_validation(data),
                ]
                if schema_healing_events and self._schema_healing_mode == "strict":
                    raise FormalizerSchemaValidationError(
                        "LLM formalizer output required schema healing in strict mode.",
                        phase="schema_healing",
                        field_errors=schema_healing_events,
                        draft_id=draft.draft_id,
                    )
                bundle = TrinityBundle.model_validate(data)
                if schema_version and bundle.schema_version != schema_version:
                    bundle = bundle.model_copy(update={"schema_version": schema_version})
                return _normalize_trinity_bundle_for_linker(bundle)
            except FormalizerSchemaValidationError:
                raise
            except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
                last_error = str(exc)
                last_schema_error = str(exc)

        if self._schema_healing_mode == "strict" and last_schema_error:
            raise FormalizerSchemaValidationError(
                "LLM formalizer output failed TrinityBundle schema validation in strict mode.",
                phase="schema_validation",
                field_errors=[{"path": "TrinityBundle", "error": last_schema_error}],
                draft_id=draft.draft_id,
            )

        # Fallback to deterministic formalizer if LLM output is unusable.
        emit_degraded_path(
            component="agent.formalizer",
            operation="formalize",
            reason="deterministic_fallback",
            message=last_error or "LLM formalization did not yield a valid TrinityBundle",
            error_type="FormalizerFallback",
            details={"draft_id": draft.draft_id, "max_retries": self.MAX_RETRIES},
            log=logger,
        )
        return await self._fallback.formalize(
            draft,
            schema_version=schema_version,
        )

    async def repair_ir(
        self,
        ir: TrinityBundle,
        errors: list[str],
        *,
        hint: str | None = None,
    ) -> TrinityBundle:
        return await self._fallback.repair_ir(
            ir,
            errors,
            hint=hint,
        )

    async def validate_structure(
        self,
        ir: TrinityBundle,
    ) -> tuple[bool, list[str]]:
        return await self._fallback.validate_structure(ir)


def create_mock_draft(
    *,
    draft_id: str | None = None,
    problem_frame_ref: str = "pf_mock",
    narrative: str = "Mock policy to reduce poverty through targeted subsidies",
    interventions: list[dict[str, Any]] | None = None,
) -> DraftResult:
    """Create mock draft."""
    import uuid

    return DraftResult(
        draft_id=draft_id or f"draft_{uuid.uuid4().hex[:8]}",
        problem_frame_ref=problem_frame_ref,
        narrative=narrative,
        interventions=interventions or [],
        rationale="Mock rationale for testing",
        confidence=0.85,
        created_at=datetime.now(UTC),
    )


def _verify_protocol() -> None:
    agent = MockFormalizerAgent()
    if not isinstance(agent, FormalizerAgent):
        raise TypeError("MockFormalizerAgent does not implement FormalizerAgent protocol")


_verify_protocol()
