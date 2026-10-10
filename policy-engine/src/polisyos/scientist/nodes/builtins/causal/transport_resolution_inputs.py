"""Context, configuration, and registry helpers for transport resolution."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.data_forge.read_api.academic import SKGQuery
from polisyos.data_forge.read_api.catalog import DatasetRegistry, PStarZResult
from polisyos.foundry.methods.catalog.causal.capabilities import (
    build_causal_capability_contract,
)
from polisyos.ir.analytics import CausalEffectReport
from polisyos.ir.analytics.causal_capabilities import (
    CausalCapabilityContract,
    load_causal_capability_contract,
    persist_causal_capability_contract,
)
from polisyos.ir.analytics.causal_ensemble import load_causal_model_ensemble
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    PAGIdentificationPolicy,
    load_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.privacy_transportability import (
    TransportPrivacyContext,
    coerce_transport_privacy_context,
)
from polisyos.ir.registry.refs import (
    CausalCapabilityContractRef,
    CausalGraphModelRef,
    CausalModelEnsembleRef,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

logger = get_logger("polisyos.scientist.nodes.builtins.causal.resolve_transport")

_TRANSPORT_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_TRANSPORT_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)
_TRANSPORT_NUMERIC_PARSE_ERRORS = (TypeError, ValueError, OverflowError)
_VALID_TRANSPORT_SOLVER_MODES: frozenset[str] = frozenset(
    {"auto", "simplified", "symbolic", "symbolic_y0", "symbolic_r", "full_auto"}
)


class InvalidTransportInput(ValueError):
    """Identify an explicitly supplied transport value that cannot be consumed safely."""


def _read_optional_name(raw: Any, field: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidTransportInput(f"params.{field} must be a non-empty string when supplied")
    return raw.strip()


def _read_finite_number(raw: Any, field: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float, Decimal, str)):
        raise InvalidTransportInput(f"{field} must be a finite number when supplied")
    try:
        parsed = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidTransportInput(f"{field} must be a finite number when supplied") from exc
    if not math.isfinite(parsed):
        raise InvalidTransportInput(f"{field} must be a finite number when supplied")
    return parsed


def _read_integer(raw: Any, field: str) -> int:
    if isinstance(raw, bool):
        raise InvalidTransportInput(f"{field} must be an integer when supplied")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and math.isfinite(raw) and raw.is_integer():
        return int(raw)
    if isinstance(raw, str):
        token = raw.strip()
        digits = token[1:] if token[:1] in {"+", "-"} else token
        if digits and digits.isdigit():
            try:
                return int(token)
            except ValueError as exc:
                raise InvalidTransportInput(f"{field} must be an integer when supplied") from exc
    raise InvalidTransportInput(f"{field} must be an integer when supplied")


class _NullDatasetRegistry:
    def find_datasets_for_variable(
        self,
        canonical_var: str,
        country_code: str,
        year_range: tuple[int, int] | None = None,
    ) -> list[Any]:
        del canonical_var, country_code, year_range
        return []

    def compute_p_star_z(
        self,
        canonical_var: str,
        country_code: str,
        year: int,
        *,
        condition_on: dict[str, float] | None = None,
    ) -> PStarZResult:
        del country_code, year
        return PStarZResult(
            canonical_variable=canonical_var,
            value=None,
            dataset_id=None,
            raw_variable=None,
            is_proxy=False,
            confidence=0.0,
            penalty_breakdown={"missing_registry": 1.0},
            is_conditional=bool(condition_on),
            condition_on=condition_on or {},
        )


class _NullSKG:
    def query_claims(self, *, cause: str, effect: str, min_trust: float = 0.0) -> list[Any]:
        del cause, effect, min_trust
        return []


class _LoopDatasetRegistry:
    """Per-run cached view over dataset lookups used by resolution loop."""

    def __init__(
        self,
        *,
        find_cached: Callable[[str, str, tuple[int, int] | None], list[Any]],
        p_star_cached: Callable[[str, str, int, dict[str, float] | None], PStarZResult],
    ) -> None:
        self._find_cached = find_cached
        self._p_star_cached = p_star_cached

    def find_datasets_for_variable(
        self,
        canonical_var: str,
        country_code: str,
        year_range: tuple[int, int] | None = None,
    ) -> list[Any]:
        return self._find_cached(canonical_var, country_code, year_range)

    def compute_p_star_z(
        self,
        canonical_var: str,
        country_code: str,
        year: int,
        *,
        condition_on: dict[str, float] | None = None,
    ) -> PStarZResult:
        return self._p_star_cached(canonical_var, country_code, year, condition_on)


def _transport_execution_profile(state: ExperimentState) -> str:
    raw_profile = state.execution_profile or state.params.get("execution_profile") or ""
    return str(raw_profile).strip().lower()


def _resolve_query_treatment_for_blocking(
    state: ExperimentState,
    report: CausalEffectReport | None,
) -> str:
    if report is not None:
        return _resolve_query_treatment(state, report)
    raw = _read_optional_name(state.params.get("query_treatment"), "query_treatment")
    return raw if raw is not None else "treatment"


def _resolve_query_outcome_for_blocking(
    state: ExperimentState,
    report: CausalEffectReport | None,
) -> str:
    if report is not None:
        return _resolve_query_outcome(state, report)
    raw = _read_optional_name(state.params.get("query_outcome"), "query_outcome")
    return raw if raw is not None else "outcome"


def _context_id_for_blocking(profile: ContextProfile | None, raw: Any) -> str:
    if profile is not None and profile.context_id:
        return profile.context_id
    if isinstance(raw, Mapping):
        raw_context_id = raw.get("context_id")
        if isinstance(raw_context_id, str) and raw_context_id.strip():
            return raw_context_id.strip()
    return ""


def _resolve_query_treatment(state: ExperimentState, report: CausalEffectReport) -> str:
    raw = _read_optional_name(state.params.get("query_treatment"), "query_treatment")
    if raw is not None:
        return raw
    for key in ("query_treatment", "treatment", "treatment_name"):
        value = _read_optional_name(report.method_params.get(key), f"report.method_params.{key}")
        if value is not None:
            return value
    value = _read_optional_name(
        report.metadata.get("query_treatment"), "report.metadata.query_treatment"
    )
    if value is not None:
        return value
    return "treatment"


def _resolve_query_outcome(state: ExperimentState, report: CausalEffectReport) -> str:
    raw = _read_optional_name(state.params.get("query_outcome"), "query_outcome")
    if raw is not None:
        return raw
    for key in ("query_outcome", "outcome", "outcome_name"):
        value = _read_optional_name(report.method_params.get(key), f"report.method_params.{key}")
        if value is not None:
            return value
    return "outcome"


def _resolve_treatment_value(policy_spec: Mapping[str, Any] | None) -> float:
    if not policy_spec:
        return 1.0
    for key in ("query_treatment_value", "treatment_value", "value", "dose"):
        raw = policy_spec.get(key)
        if raw is None:
            continue
        return _read_finite_number(raw, f"policy_spec.{key}")
    return 1.0


def _resolve_context_year(context: ContextProfile) -> int:
    if context.publication_year is not None:
        return int(context.publication_year)
    token = (context.time_period or "").strip()
    for chunk in token.replace("/", "-").split("-"):
        chunk = chunk.strip()
        if len(chunk) == 4 and chunk.isdigit():
            return int(chunk)
    return 2020


def _resolve_context_profile(raw: Any) -> ContextProfile | None:
    if isinstance(raw, ContextProfile):
        return raw
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        try:
            return ContextProfile.model_validate(raw)
        except _TRANSPORT_VALIDATION_ERRORS as exc:
            raise InvalidTransportInput("context profile is malformed") from exc
    raise InvalidTransportInput("context profile must be an object when supplied")


def _normalize_transport_solver_mode(raw: Any) -> str:
    if raw is None:
        return "auto"
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidTransportInput("transport_solver_mode must be a supported string")
    token = raw.strip().lower()
    if token not in _VALID_TRANSPORT_SOLVER_MODES:
        raise InvalidTransportInput(f"transport_solver_mode is unsupported: {token!r}")
    return token


def _resolve_transport_solver_mode(state: ExperimentState) -> str:
    return _normalize_transport_solver_mode(state.params.get("transport_solver_mode"))


def _resolve_allow_degraded_transport(state: ExperimentState) -> bool:
    raw = state.params.get("allow_degraded_transport")
    profile = (
        str(state.execution_profile or state.params.get("execution_profile") or "").strip().lower()
    )
    if isinstance(raw, bool):
        if raw and profile != "dev":
            raise InvalidTransportInput(
                "allow_degraded_transport is forbidden outside the dev execution profile"
            )
        return raw
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token in {"1", "true", "yes", "on"}:
            if profile != "dev":
                raise InvalidTransportInput(
                    "allow_degraded_transport is forbidden outside the dev execution profile"
                )
            return True
        if token in {"0", "false", "no", "off"}:
            return False
        raise InvalidTransportInput("params.allow_degraded_transport must be boolean when supplied")
    if raw is not None:
        raise InvalidTransportInput("params.allow_degraded_transport must be boolean when supplied")
    workflow_id = str(state.params.get("workflow_id", "")).strip().lower()
    if workflow_id == "scientist_causal_full":
        return False
    return False


def _resolve_or_build_capability_contract(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> tuple[CausalCapabilityContract, CausalCapabilityContractRef]:
    raw_ref = state.artifacts_index.get(ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF)
    if raw_ref is not None:
        try:
            ref = CausalCapabilityContractRef.model_validate(raw_ref.model_dump(mode="json"))
            return load_causal_capability_contract(_ensure_ir_artifact_store(ctx.store), ref), ref
        except _TRANSPORT_LOAD_ERRORS:
            logger.debug(
                "Failed to load causal capability contract from ref %s, rebuilding",
                raw_ref,
                exc_info=True,
            )
    contract = build_causal_capability_contract()
    ref = persist_causal_capability_contract(_ensure_ir_artifact_store(ctx.store), contract)
    return contract, ref


def _resolve_pag_identification_policy(state: ExperimentState, graph: CausalGraphModel) -> str:
    raw = state.params.get("pag_identification_policy")
    if raw is not None:
        if not isinstance(raw, str) or not raw.strip():
            raise InvalidTransportInput(
                "params.pag_identification_policy must be a supported string"
            )
        token = raw.strip().lower()
        try:
            return PAGIdentificationPolicy(token).value
        except ValueError as exc:
            raise InvalidTransportInput(
                f"params.pag_identification_policy is unsupported: {token!r}"
            ) from exc
    if graph.graph_type.value == "pag":
        return "probabilistic"
    return "conservative"


def _resolve_pag_max_dag_samples(
    state: ExperimentState,
    *,
    normalization_warnings: list[str] | None = None,
) -> int:
    raw = state.params.get("pag_max_dag_samples")
    if raw is None:
        return 100
    parsed = _read_integer(raw, "params.pag_max_dag_samples")
    bounded = min(max(parsed, 1), 500)
    if bounded != parsed and normalization_warnings is not None:
        normalization_warnings.append(
            f"pag_max_dag_samples clamped from {parsed} to {bounded} (supported range 1..500)"
        )
    return bounded


def _resolve_pag_threshold(
    state: ExperimentState,
    *,
    normalization_warnings: list[str] | None = None,
) -> float:
    raw = state.params.get("pag_threshold")
    if raw is None:
        return 0.5
    parsed = _read_finite_number(raw, "params.pag_threshold")
    bounded = min(max(parsed, 0.0), 1.0)
    if bounded != parsed and normalization_warnings is not None:
        normalization_warnings.append(
            f"pag_threshold clamped from {parsed} to {bounded} (supported range 0..1)"
        )
    return bounded


def _resolve_pag_seed(state: ExperimentState, graph: CausalGraphModel) -> int:
    raw = state.params.get("pag_seed")
    if raw is not None:
        parsed = _read_integer(raw, "params.pag_seed")
        if not 0 <= parsed <= 2**32 - 1:
            raise InvalidTransportInput("params.pag_seed must be in range 0..4294967295")
        return parsed
    payload = f"{state.run_id}|{graph.model_dump_json(exclude_none=False, by_alias=True)}"
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16) % (2**31 - 1)


@dataclass(frozen=True)
class _TransportExecutionInputs:
    query_treatment: str
    query_outcome: str
    policy_spec: Mapping[str, Any] | None
    pag_identification_policy: str
    pag_max_dag_samples: int
    pag_threshold: float
    pag_seed: int
    solver_mode: str
    allow_degraded_transport: bool
    privacy_context: TransportPrivacyContext | None
    normalization_warnings: tuple[str, ...]


def _resolve_transport_execution_inputs(
    state: ExperimentState,
    report: CausalEffectReport,
    graph: CausalGraphModel,
    *,
    privacy_context_resolver: Callable[[Mapping[str, Any]], TransportPrivacyContext | None]
    | None = None,
) -> _TransportExecutionInputs:
    query_treatment = _resolve_query_treatment(state, report)
    query_outcome = _resolve_query_outcome(state, report)
    policy_spec_raw = state.params.get("policy_spec")
    if policy_spec_raw is not None and not isinstance(policy_spec_raw, Mapping):
        raise InvalidTransportInput("params.policy_spec must be an object when supplied")
    policy_spec = policy_spec_raw
    _resolve_treatment_value(policy_spec)
    for field in (
        "dataset_registry_db_path",
        "legal_kg_db_path",
        "skg_db_path",
        "skg_index_dir",
    ):
        _coerce_path(state.params.get(field), field=f"params.{field}")
    resolve_privacy_context = privacy_context_resolver or _resolve_transport_privacy_context
    privacy_context = resolve_privacy_context(state.params)

    normalization_warnings: list[str] = []
    return _TransportExecutionInputs(
        query_treatment=query_treatment,
        query_outcome=query_outcome,
        policy_spec=policy_spec,
        pag_identification_policy=_resolve_pag_identification_policy(state, graph),
        pag_max_dag_samples=_resolve_pag_max_dag_samples(
            state,
            normalization_warnings=normalization_warnings,
        ),
        pag_threshold=_resolve_pag_threshold(
            state,
            normalization_warnings=normalization_warnings,
        ),
        pag_seed=_resolve_pag_seed(state, graph),
        solver_mode=_resolve_transport_solver_mode(state),
        allow_degraded_transport=_resolve_allow_degraded_transport(state),
        privacy_context=privacy_context,
        normalization_warnings=tuple(normalization_warnings),
    )


def _build_graph_ref_from_artifact_id(artifact_id: str) -> CausalGraphModelRef | None:
    try:
        return CausalGraphModelRef.model_validate(
            {
                "artifact_id": artifact_id,
                "kind": "ir.causal_graph_model",
                "media_type": "application/json",
            }
        )
    except _TRANSPORT_VALIDATION_ERRORS:
        return None


def _resolve_causal_graph(ctx: ExecutionContext, state: ExperimentState) -> CausalGraphModel | None:
    ensemble_ref_raw = state.artifacts_index.get(ARTIFACT_CAUSAL_ENSEMBLE_REF)
    if ensemble_ref_raw is not None:
        try:
            ensemble_ref = CausalModelEnsembleRef.model_validate(
                ensemble_ref_raw.model_dump(mode="json")
            )
            ensemble = load_causal_model_ensemble(
                _ensure_ir_artifact_store(ctx.store), ensemble_ref
            )
            if ensemble.consensus_graph_ref:
                consensus_ref = _build_graph_ref_from_artifact_id(ensemble.consensus_graph_ref)
                if consensus_ref is not None:
                    return load_causal_graph_model(
                        _ensure_ir_artifact_store(ctx.store), consensus_ref
                    )
        except _TRANSPORT_LOAD_ERRORS:
            logger.debug(
                "Failed to load causal graph from ensemble ref %s; trying fallback refs",
                ensemble_ref_raw,
                exc_info=True,
            )

    for key in (ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF, "causal_graph_ref"):
        ref_raw = state.artifacts_index.get(key)
        if ref_raw is None:
            continue
        try:
            graph_ref = CausalGraphModelRef.model_validate(ref_raw.model_dump(mode="json"))
            return load_causal_graph_model(_ensure_ir_artifact_store(ctx.store), graph_ref)
        except _TRANSPORT_LOAD_ERRORS:
            continue
    return None


def _build_dataset_registry(raw_path: Any) -> DatasetRegistry | _NullDatasetRegistry:
    path = _coerce_path(raw_path)
    if path is None or not path.exists():
        return _NullDatasetRegistry()
    return DatasetRegistry(path)


def build_skg_query(
    db_path: Any,
    index_dir: Any,
    *,
    query_type: Any = SKGQuery,
) -> SKGQuery | _NullSKG:
    db = _coerce_path(db_path)
    if db is None or not db.exists():
        return _NullSKG()
    index = _coerce_path(index_dir) or db.parent
    try:
        return query_type(db_path=db, index_dir=index)
    except _TRANSPORT_LOAD_ERRORS:
        return _NullSKG()


def _coerce_path(raw: Any, *, field: str = "path") -> Path | None:
    if raw is None:
        return None
    if isinstance(raw, Path):
        if not str(raw).strip():
            raise InvalidTransportInput(
                f"{field} must be a non-empty filesystem path when supplied"
            )
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise InvalidTransportInput(
                f"{field} must be a non-empty filesystem path when supplied"
            )
        return Path(text)
    raise InvalidTransportInput(f"{field} must be a filesystem path string when supplied")


def _resolve_transport_privacy_context(
    params: Mapping[str, Any],
) -> TransportPrivacyContext | None:
    for field in (
        "privacy_context",
        "dp_utility_manifest",
        "privacy_transport_certificate",
    ):
        candidate = params.get(field)
        if candidate is None:
            continue
        context = coerce_transport_privacy_context(candidate)
        if context is not None:
            return context
        raise InvalidTransportInput(f"params.{field} is malformed or unsupported")
    return None
