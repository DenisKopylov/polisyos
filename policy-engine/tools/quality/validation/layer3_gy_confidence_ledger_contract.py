"""Narrow owner adapters for the GY-N11 confidence ledger contract.

The adapter is intentionally not an authority owner.  It reopens N10 through
``check_layer3_gy_depth_n_universality_contract`` and N13a's public route
projection, then reopens N13b through
``layer3_gy_n13b_acquisition_contract`` and the canonical runtime admission
passport owner.  It projects only the evidence needed by N11 and caches the
resulting immutable bundle behind a content-derived invalidation fence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_N10_CAPSTONE = Path(
    "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json"
)
DEFAULT_N13B_CONTRACT = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_executor_contract.json"
)
DEFAULT_N13B_REENTRY_TRACE = Path(
    "architecture/policy_design_case/layer3_gy_n13b_reentry_trace.json"
)
DEFAULT_N13B_REGISTRY = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_registry.json"
)
DEFAULT_N13B_JOURNAL = Path(
    "architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
)
DEFAULT_N13B_CAS = Path("architecture/policy_design_case/layer3_gy_acquisition_cas")
DEFAULT_GENERATED_ARTIFACTS = Path("architecture/generated_artifacts.toml")

_OWNER_PROGRESS_CALLBACK: ContextVar[Callable[[str], None] | None] = ContextVar(
    "n11_owner_progress_callback",
    default=None,
)


class OwnerProjectionError(RuntimeError):
    """Fail-closed error raised when a projected owner cannot be recomputed."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(f"{code}: {self.detail}")


@dataclass(frozen=True)
class N10RouteOwnerProjection:
    """One N10 route projected through N13a's public owner algebra."""

    route_id: str
    domain_role: str
    demanded_metrics: tuple[str, ...]
    witness_kind: str
    candidate_ref: str
    requirement_gap_id: str
    gap_source: str
    row_addressable_variable: str | None
    planner_gap_kind: str
    planner_strategy_kind: str
    blocker_codes: tuple[str, ...]
    missing_requirement_fields: tuple[str, ...]
    missing_link: str
    projection_sha256: str


@dataclass(frozen=True)
class N10OwnerProjection:
    """Complete narrow denominator of real N10 refusal/acquisition routes."""

    source_ref: str
    source_projection_scope: str
    source_projection_sha256: str
    routes: tuple[N10RouteOwnerProjection, ...]
    route_count: int
    witness_kind_counts: tuple[tuple[str, int], ...]
    owner_acquisition_route_count: int
    estimand_binding_refusal_count: int
    owner_data_gap_count: int
    projection_sha256: str


@dataclass(frozen=True)
class N13bAttemptOwnerProjection:
    """One exact terminal attempt from the recomputed N13b journal projection."""

    attempt_id: str
    call_class: str
    request_variables: tuple[str, ...]
    failure_code: str
    outcome_code: str
    raw_evidence_event_sha256: str | None
    raw_body_sha256: str | None
    raw_cas_persisted: bool
    quarantine: bool
    response_admitted: bool
    projection_sha256: str


@dataclass(frozen=True)
class N13bPassportOwnerProjection:
    """One admission passport after public resolve-bind-verify revalidation."""

    passport_id: str
    epoch_id: int
    variable_id: str
    source_lane: str
    observation_class: str
    authority_entry_id: str
    authority_provision_id: str
    authority_registry_content_sha256: str
    raw_evidence_event_sha256: str
    raw_artifact_id: str
    source_watermark: str
    status: str
    rejection_codes: tuple[str, ...]
    projection_sha256: str


@dataclass(frozen=True)
class N13bOwnerProjection:
    """Narrow exact N13b state used to account admission and refusal evidence."""

    source_ref: str
    source_accounting_projection_scope: str
    source_accounting_projection_sha256: str
    authority_projection_sha256: str
    baseline_sha256: str
    l5_measurement_registry_sha256: str
    authority_registry_content_sha256: str
    authority_registry_entry_count: int
    provision_id: str
    live_harness_receipt_count: int
    local_rights_trust_anchor_sha256: str | None
    journal_projection_sha256: str
    journal_event_count: int
    journal_request_count: int
    live_attempt_count: int
    raw_response_count: int
    persisted_raw_response_count: int
    response_admitted_count: int
    quarantine_count: int
    attempts: tuple[N13bAttemptOwnerProjection, ...]
    quarantine_projection_sha256: str
    quarantine_disposition: str
    terminal_without_response_count: int
    quarantine_failure_code_counts: tuple[tuple[str, int], ...]
    overlay_exists: bool
    overlay_content_sha256: str | None
    overlay_epoch_count: int
    overlay_registration_count: int
    overlay_admitted_observation_count: int
    passport_count: int
    passports: tuple[N13bPassportOwnerProjection, ...]
    reentry_projection_sha256: str
    world_growth_projection_sha256: str
    world_growth_target_variable: str
    availability_count_before: int
    availability_count_after: int
    world_growth_status: str
    world_growth_event_count: int
    availability_count_delta: int
    terminal_disposition: str
    capstone_route_projection_sha256: str
    projection_sha256: str


@dataclass(frozen=True)
class OwnerEvidenceBundle:
    """Content-keyed, immutable owner evidence consumed by N11."""

    n10: N10OwnerProjection
    n13b: N13bOwnerProjection
    projection_sha256: str


def load_owner_bundle(
    repo_root: Path,
    *,
    catalog_path: Path,
    l5_path: Path,
    objective_progress: Callable[[str], None] | None = None,
) -> OwnerEvidenceBundle:
    """Recompute and cache the real N10/N13b narrow owner projections.

    The cache key includes current catalog, L5, registry, frozen projection,
    source-owner, evidence-owner, journal, CAS, and overlay content identities.
    Hashes of whole contracts are used only as private invalidation inputs and
    are never exported as N11 provenance.

    Args:
        repo_root: Policy Engine checkout root.
        catalog_path: Immutable N13b epoch-zero catalog.
        l5_path: N13b measurement trust registry.
        objective_progress: Optional observer for monotone derivation milestones.

    Returns:
        A narrow, immutable owner evidence bundle.

    Raises:
        OwnerProjectionError: If any owner is missing, stale, forged, or cannot
            be structurally recomputed.
    """

    root = Path(repo_root).resolve()
    catalog = Path(catalog_path).resolve()
    l5 = Path(l5_path).resolve()
    token = _OWNER_PROGRESS_CALLBACK.set(objective_progress)
    try:
        _report_owner_progress("owner_pre_derivation_fence_started")
        cache_fence = _owner_cache_fence(root, catalog_path=catalog, l5_path=l5)
        _report_owner_progress("owner_pre_derivation_fence_complete")
        bundle = _load_owner_bundle_cached(
            root.as_posix(),
            catalog.as_posix(),
            l5.as_posix(),
            cache_fence,
        )
        _report_owner_progress("owner_post_derivation_fence_started")
        post_derivation_fence = _owner_cache_fence(
            root,
            catalog_path=catalog,
            l5_path=l5,
        )
        _report_owner_progress("owner_post_derivation_fence_complete")
        if post_derivation_fence != cache_fence:
            raise OwnerProjectionError("owner_cache_fence_changed_during_derivation")
        _report_owner_progress("owner_bundle_fence_validated")
        return bundle
    finally:
        _OWNER_PROGRESS_CALLBACK.reset(token)


def clear_owner_bundle_cache() -> None:
    """Clear the warm owner bundle cache used by focused tests and writers."""

    _load_owner_bundle_cached.cache_clear()


def owner_bundle_cache_stats() -> dict[str, int]:
    """Return deterministic counters for the process-local owner cache."""

    info = _load_owner_bundle_cached.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize or 0,
        "currsize": info.currsize,
    }


@lru_cache(maxsize=4)
def _load_owner_bundle_cached(
    repo_root: str,
    catalog_path: str,
    l5_path: str,
    _cache_fence: str,
) -> OwnerEvidenceBundle:
    root = Path(repo_root)
    catalog = Path(catalog_path)
    l5 = Path(l5_path)
    _report_owner_progress("n10_owner_recomputation_started")
    capstone = _recompute_n10_capstone(root)
    _report_owner_progress("n10_owner_recomputation_complete")
    _report_owner_progress("n13b_owner_recomputation_started")
    contract = _recompute_n13b_contract(root, catalog_path=catalog, l5_path=l5)
    _report_owner_progress("n13b_owner_recomputation_complete")
    n10 = _project_n10(capstone)
    _report_owner_progress("n10_owner_projection_complete")
    n13b = _project_n13b(
        repo_root=root,
        catalog_path=catalog,
        l5_path=l5,
        contract=contract,
        n10=n10,
    )
    _report_owner_progress("n13b_owner_projection_complete")
    values = {"n10": asdict(n10), "n13b": asdict(n13b)}
    return OwnerEvidenceBundle(
        n10=n10,
        n13b=n13b,
        projection_sha256=_content_sha256(values),
    )


def _report_owner_progress(milestone: str) -> None:
    callback = _OWNER_PROGRESS_CALLBACK.get()
    if callback is not None:
        callback(milestone)


def _recompute_n10_capstone(repo_root: Path) -> dict[str, Any]:
    path = Path(repo_root) / DEFAULT_N10_CAPSTONE
    stored = _read_json_mapping(path, owner="n10_capstone")
    _validate_n10_payload(stored)
    stored_routes = _extract_n10_route_projection(stored)
    try:
        recomputed = _build_n10_cached_payload(Path(repo_root))
    except OwnerProjectionError:
        raise
    except Exception as exc:  # noqa: BLE001 - fail-closed owner boundary
        raise OwnerProjectionError("n10_capstone_recompute_failed", type(exc).__name__) from exc
    _validate_n10_payload(recomputed)
    recomputed_routes = _extract_n10_route_projection(recomputed)
    if stored_routes != recomputed_routes:
        raise OwnerProjectionError("n10_capstone_route_projection_drift")
    return recomputed


def _validate_n10_payload(payload: Mapping[str, Any]) -> None:
    from tools.quality.validation.check_layer3_gy_depth_n_universality_contract import (
        validate_payload,
    )

    try:
        report = validate_payload(payload)
    except Exception as exc:  # noqa: BLE001 - fail-closed owner boundary
        raise OwnerProjectionError("n10_capstone_validation_failed", str(exc)) from exc
    if report.get("status") != "pass":
        issues = report.get("issues")
        raise OwnerProjectionError("n10_capstone_invalid", repr(issues))


def _build_n10_cached_payload(repo_root: Path) -> dict[str, Any]:
    from tools.quality.validation.check_layer3_gy_depth_n_universality_contract import (
        build_live_payload,
        check_provenance_stability,
    )

    # The cached capstone owner replays async generation-cycle recordings.  Prime
    # its synchronous provenance owner first so the composition validator runs
    # outside that event loop; this is the same ordering used by the N10 checker.
    stability = check_provenance_stability(repo_root)
    if stability.get("status") != "stable":
        raise OwnerProjectionError(
            "n10_capstone_provenance_unstable",
            repr(stability.get("issues")),
        )
    return build_live_payload(repo_root, lane="cached")


def _extract_n10_route_projection(payload: Mapping[str, Any]) -> object:
    """Resolve N11's narrow N10 route projection through the N13a owner."""

    from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
        extract_route_projection,
    )

    try:
        return extract_route_projection(
            capstone=payload,
            capstone_source=DEFAULT_N10_CAPSTONE.as_posix(),
        )
    except Exception as exc:  # noqa: BLE001 - fail-closed owner boundary
        raise OwnerProjectionError("n10_route_projection_invalid", str(exc)) from exc


def _recompute_n13b_contract(
    repo_root: Path,
    *,
    catalog_path: Path,
    l5_path: Path,
) -> Any:
    from pydantic import ValidationError

    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        N13bAcquisitionExecutorContract,
        derive_n13b_acquisition_executor_contract,
    )

    path = Path(repo_root) / DEFAULT_N13B_CONTRACT
    try:
        stored = N13bAcquisitionExecutorContract.model_validate_json(path.read_bytes())
        recomputed = derive_n13b_acquisition_executor_contract(
            repo_root=repo_root,
            baseline_sha256=_file_sha256(catalog_path),
            l5_sha256=_file_sha256(l5_path),
        )
    except OwnerProjectionError:
        raise
    except (OSError, ValidationError, ValueError, RuntimeError) as exc:
        raise OwnerProjectionError("n13b_owner_recompute_failed", str(exc)) from exc
    stored_projection = _extract_n13b_accounting_projection(stored)
    recomputed_projection = _extract_n13b_accounting_projection(recomputed)
    if stored_projection != recomputed_projection:
        raise OwnerProjectionError("n13b_accounting_projection_drift")
    return recomputed


def _n13b_accounting_projection_sha256(
    contract: Any,
    *,
    passports: tuple[N13bPassportOwnerProjection, ...] = (),
) -> str:
    """Return the content identity of N11's declared N13b projection."""

    return _content_sha256(
        {
            "projection_scope": "n13b_confidence_accounting",
            "source_ref": DEFAULT_N13B_CONTRACT.as_posix(),
            "contract_projection": _extract_n13b_accounting_projection(contract),
            "revalidated_passports": tuple(asdict(row) for row in passports),
        }
    )


def _extract_n13b_accounting_projection(contract: Any) -> dict[str, object]:
    """Return only the N13b evidence projection declared for N11.

    Actual passport identities are deliberately absent from the frozen N13b
    contract.  ``_load_revalidated_passports`` enumerates them from the bound
    overlay and resolves, binds, and revalidates every passport before N11 can
    account it.  This frozen-owner comparison therefore binds the admission
    denominator that controls that enumeration, not unrelated N13b lifecycle,
    derivation, carrier, or resumption-budget fields.
    """

    return {
        "authority_owner": contract.authority_owner.model_dump(mode="json"),
        "quarantine": contract.quarantine.model_dump(mode="json"),
        "world_growth": contract.world_growth.model_dump(mode="json"),
        "admission_passport_denominator": {
            "response_admitted_count": contract.journal.response_admitted_count,
            "quarantine_response_admitted_count": (contract.quarantine.response_admitted_count),
            "overlay_admitted_observation_count": (
                contract.quarantine.overlay_admitted_observation_count
            ),
            "world_growth_admitted_observation_count": (
                contract.world_growth.admitted_observation_count
            ),
        },
    }


def _project_n10(capstone: Mapping[str, Any]) -> N10OwnerProjection:
    from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
        extract_route_projection,
    )

    try:
        projection = extract_route_projection(
            capstone=capstone,
            capstone_source=DEFAULT_N10_CAPSTONE.as_posix(),
        )
    except Exception as exc:  # noqa: BLE001 - fail-closed owner boundary
        raise OwnerProjectionError("n10_route_projection_invalid", str(exc)) from exc
    rows: list[N10RouteOwnerProjection] = []
    for route in projection.routes:
        values = route.model_dump(mode="json")
        rows.append(
            N10RouteOwnerProjection(
                route_id=route.route_id,
                domain_role=route.domain_role,
                demanded_metrics=route.demanded_metrics,
                witness_kind=route.witness_kind,
                candidate_ref=route.candidate_ref,
                requirement_gap_id=route.requirement_gap_id,
                gap_source=route.gap_source,
                row_addressable_variable=route.row_addressable_variable,
                planner_gap_kind=route.planner_gap_kind,
                planner_strategy_kind=route.planner_strategy_kind,
                blocker_codes=route.blocker_codes,
                missing_requirement_fields=route.missing_requirement_fields,
                missing_link=route.missing_link,
                projection_sha256=_content_sha256(values),
            )
        )
    ordered = tuple(sorted(rows, key=lambda row: row.route_id))
    witness_counts: dict[str, int] = {}
    for row in ordered:
        witness_counts[row.witness_kind] = witness_counts.get(row.witness_kind, 0) + 1
    values = {
        "source_ref": DEFAULT_N10_CAPSTONE.as_posix(),
        "source_projection_scope": projection.projection_binding.projection_id,
        "source_projection_sha256": (projection.projection_binding.projection_content_sha256),
        "routes": ordered,
        "route_count": len(ordered),
        "witness_kind_counts": tuple(sorted(witness_counts.items())),
        "owner_acquisition_route_count": sum(
            row.witness_kind == "owner_acquisition_route" for row in ordered
        ),
        "estimand_binding_refusal_count": sum(
            row.witness_kind == "estimand_binding_refusal" for row in ordered
        ),
        "owner_data_gap_count": sum(row.witness_kind == "owner_data_gap" for row in ordered),
    }
    hash_values = {
        key: tuple(asdict(row) for row in value) if key == "routes" else value
        for key, value in values.items()
    }
    return N10OwnerProjection(
        **values,
        projection_sha256=_content_sha256(hash_values),
    )


def _project_n13b(
    *,
    repo_root: Path,
    catalog_path: Path,
    l5_path: Path,
    contract: Any,
    n10: N10OwnerProjection,
) -> N13bOwnerProjection:
    trace = _read_reentry_trace(repo_root)
    _require_n13b_projection_coherence(contract=contract, trace=trace, n10=n10)
    passports = _load_revalidated_passports(
        repo_root=repo_root,
        catalog_path=catalog_path,
        l5_path=l5_path,
        overlay_state=trace.overlay_state,
        expected_response_admitted_count=contract.journal.response_admitted_count,
    )
    attempts = tuple(
        N13bAttemptOwnerProjection(
            attempt_id=row.attempt_id,
            call_class=row.call_class,
            request_variables=row.request_variables,
            failure_code=row.failure_code,
            outcome_code=row.outcome_code,
            raw_evidence_event_sha256=row.raw_evidence_event_sha256,
            raw_body_sha256=row.raw_body_sha256,
            raw_cas_persisted=row.raw_cas_persisted,
            quarantine=row.quarantine,
            response_admitted=row.response_admitted,
            projection_sha256=row.projection_sha256,
        )
        for row in contract.journal.attempts
    )
    state = trace.overlay_state
    values = {
        "source_ref": DEFAULT_N13B_CONTRACT.as_posix(),
        "source_accounting_projection_scope": "n13b_confidence_accounting",
        "source_accounting_projection_sha256": _n13b_accounting_projection_sha256(
            contract,
            passports=passports,
        ),
        "authority_projection_sha256": contract.authority_owner.projection_sha256,
        "baseline_sha256": contract.authority_owner.baseline_sha256,
        "l5_measurement_registry_sha256": (contract.authority_owner.l5_measurement_registry_sha256),
        "authority_registry_content_sha256": (contract.authority_owner.registry_content_sha256),
        "authority_registry_entry_count": contract.authority_owner.registry_entry_count,
        "provision_id": contract.authority_owner.provision_id,
        "live_harness_receipt_count": contract.authority_owner.live_harness_receipt_count,
        "local_rights_trust_anchor_sha256": (
            contract.authority_owner.local_rights_trust_anchor_sha256
        ),
        "journal_projection_sha256": contract.journal.projection_sha256,
        "journal_event_count": contract.journal.event_count,
        "journal_request_count": contract.journal.request_count,
        "live_attempt_count": contract.journal.terminal_count,
        "raw_response_count": contract.journal.raw_response_count,
        "persisted_raw_response_count": contract.journal.persisted_raw_response_count,
        "response_admitted_count": contract.journal.response_admitted_count,
        "quarantine_count": contract.journal.quarantine_count,
        "attempts": attempts,
        "quarantine_projection_sha256": contract.quarantine.projection_sha256,
        "quarantine_disposition": contract.quarantine.disposition,
        "terminal_without_response_count": (contract.quarantine.terminal_without_response_count),
        "quarantine_failure_code_counts": tuple(
            sorted(contract.quarantine.failure_code_counts.items())
        ),
        "overlay_exists": state.exists,
        "overlay_content_sha256": state.content_sha256,
        "overlay_epoch_count": state.epoch_count,
        "overlay_registration_count": state.registration_count,
        "overlay_admitted_observation_count": state.admitted_observation_count,
        "passport_count": len(passports),
        "passports": passports,
        "reentry_projection_sha256": contract.reentry.projection_sha256,
        "world_growth_projection_sha256": contract.world_growth.projection_sha256,
        "world_growth_target_variable": contract.world_growth.target_variable,
        "availability_count_before": contract.world_growth.availability_count_before,
        "availability_count_after": contract.world_growth.availability_count_after,
        "world_growth_status": contract.world_growth.status,
        "world_growth_event_count": contract.world_growth.event_count,
        "availability_count_delta": contract.world_growth.availability_count_delta,
        "terminal_disposition": contract.world_growth.terminal_disposition,
        "capstone_route_projection_sha256": contract.capstone_routes.projection_sha256,
    }
    hash_values = {
        key: tuple(asdict(row) for row in value) if key in {"attempts", "passports"} else value
        for key, value in values.items()
    }
    return N13bOwnerProjection(
        **values,
        projection_sha256=_content_sha256(hash_values),
    )


def _read_reentry_trace(repo_root: Path) -> Any:
    from pydantic import ValidationError

    from tools.quality.validation.layer3_gy_n13b_reentry import N13bReentryTrace

    path = Path(repo_root) / DEFAULT_N13B_REENTRY_TRACE
    try:
        return N13bReentryTrace.model_validate_json(path.read_bytes())
    except (OSError, ValidationError, ValueError) as exc:
        raise OwnerProjectionError("n13b_reentry_owner_invalid", str(exc)) from exc


def _require_n13b_projection_coherence(
    *,
    contract: Any,
    trace: Any,
    n10: N10OwnerProjection,
) -> None:
    if (
        trace.trace_sha256 != contract.reentry.trace_sha256
        or trace.overlay_state.epoch_count != contract.world_growth.overlay_epoch_count
        or trace.overlay_state.admitted_observation_count
        != contract.world_growth.admitted_observation_count
    ):
        raise OwnerProjectionError("n13b_reentry_projection_drift")
    n13b_routes = {row.route_id: row for row in contract.capstone_routes.routes}
    if set(n13b_routes) != {row.route_id for row in n10.routes}:
        raise OwnerProjectionError("n10_n13b_route_denominator_drift")
    for row in n10.routes:
        preserved = n13b_routes[row.route_id]
        if preserved.witness_kind != row.witness_kind or preserved.missing_link != row.missing_link:
            raise OwnerProjectionError("n10_n13b_route_projection_drift", row.route_id)


def _load_revalidated_passports(
    *,
    repo_root: Path,
    catalog_path: Path,
    l5_path: Path,
    overlay_state: Any,
    expected_response_admitted_count: int,
) -> tuple[N13bPassportOwnerProjection, ...]:
    overlay_path = _resolve_repo_ref(repo_root, str(overlay_state.overlay_ref))
    overlay_present = overlay_path.exists() or overlay_path.is_symlink()
    claimed_count = max(
        int(expected_response_admitted_count),
        int(overlay_state.epoch_count),
        int(overlay_state.admitted_observation_count),
    )
    if not overlay_state.exists:
        if overlay_present:
            raise OwnerProjectionError("n13b_overlay_presence_drift")
        if claimed_count:
            raise OwnerProjectionError("n13b_admission_passports_unenumerable")
        return ()
    if not overlay_path.is_file():
        raise OwnerProjectionError("n13b_overlay_unreadable")
    if _file_sha256(overlay_path) != overlay_state.content_sha256:
        raise OwnerProjectionError("n13b_overlay_content_drift")

    from polisyos.data_forge.read_api import catalog as catalog_read_api

    try:
        connection = catalog_read_api.open_catalog_read_session(
            catalog_path,
            overlay_path=overlay_path,
        )
        try:
            epoch_count = _strict_db_int(
                connection.execute("SELECT count(*) FROM acquisition_epochs").fetchone()[0],
                field="epoch_count",
            )
            registration_count = _strict_db_int(
                connection.execute("SELECT count(*) FROM acquisition_registrations").fetchone()[0],
                field="registration_count",
            )
            observation_count = _strict_db_int(
                connection.execute(
                    "SELECT count(*) FROM acquisition_overlay.ds_observations"
                ).fetchone()[0],
                field="observation_count",
            )
            rows = connection.execute(
                "SELECT passport_id, epoch_id, passport_content_sha256, passport_json "
                "FROM acquisition_passports ORDER BY passport_id"
            ).fetchall()
        finally:
            connection.close()
    except Exception as exc:  # noqa: BLE001 - fail-closed owner boundary
        raise OwnerProjectionError("n13b_overlay_owner_invalid", str(exc)) from exc

    if (
        epoch_count != overlay_state.epoch_count
        or registration_count != overlay_state.registration_count
        or observation_count != overlay_state.admitted_observation_count
    ):
        raise OwnerProjectionError("n13b_overlay_count_drift")
    if len(rows) != epoch_count or expected_response_admitted_count > len(rows):
        raise OwnerProjectionError("n13b_admission_passports_unenumerable")
    if not rows:
        return ()

    from polisyos.core import artifacts

    try:
        authority = catalog_read_api.CanonicalAcquisitionAuthority.from_provision(
            repo_root=repo_root,
            baseline_path=catalog_path,
            l5_measurement_registry_path=l5_path,
        )
        artifact_store = artifacts.FileSystemCAS(Path(repo_root) / DEFAULT_N13B_CAS)
    except Exception as exc:  # noqa: BLE001 - fail-closed owner boundary
        raise OwnerProjectionError("n13b_passport_owner_unresolved", str(exc)) from exc
    projections: list[N13bPassportOwnerProjection] = []
    for row_id, row_epoch, row_content_sha256, raw_json in rows:
        if (
            type(row_id) is not str
            or type(row_epoch) is not int
            or type(row_content_sha256) is not str
            or type(raw_json) is not str
        ):
            raise OwnerProjectionError("n13b_passport_row_wire_invalid")
        try:
            payload = json.loads(raw_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise OwnerProjectionError("n13b_passport_payload_invalid", row_id) from exc
        if not isinstance(payload, dict) or _content_sha256(payload) != row_content_sha256:
            raise OwnerProjectionError("n13b_passport_content_drift", row_id)
        try:
            passport = _revalidate_passport_payload(
                payload,
                artifact_store=artifact_store,
                authority=authority,
            )
        except Exception as exc:  # noqa: BLE001 - fail-closed owner boundary
            raise OwnerProjectionError(
                "n13b_passport_revalidation_failed",
                row_id,
            ) from exc
        if passport.passport_id != row_id or passport.epoch_id != row_epoch:
            raise OwnerProjectionError("n13b_passport_row_identity_drift", row_id)
        values = {
            "passport_id": passport.passport_id,
            "epoch_id": passport.epoch_id,
            "variable_id": passport.variable_id,
            "source_lane": passport.source_lane,
            "observation_class": _enum_value(passport.observation_class),
            "authority_entry_id": passport.authority_entry_id,
            "authority_provision_id": passport.authority_provision_id,
            "authority_registry_content_sha256": (passport.authority_registry_content_sha256),
            "raw_evidence_event_sha256": passport.raw_evidence_ref.event_sha256,
            "raw_artifact_id": passport.raw_artifact_id,
            "source_watermark": passport.source_watermark,
            "status": _enum_value(passport.status),
            "rejection_codes": passport.rejection_codes,
        }
        projections.append(
            N13bPassportOwnerProjection(
                **values,
                projection_sha256=_content_sha256(values),
            )
        )
    ordered = tuple(sorted(projections, key=lambda row: row.passport_id))
    if len({row.passport_id for row in ordered}) != len(ordered):
        raise OwnerProjectionError("n13b_passport_denominator_duplicate")
    return ordered


def _revalidate_passport_payload(
    payload: Mapping[str, Any],
    *,
    artifact_store: object,
    authority: object,
) -> Any:
    from polisyos.runtime.quality.acquisition_executor import (
        AdmissionPassport,
        revalidate_admission_passport,
    )

    passport = AdmissionPassport.model_validate(payload)
    return revalidate_admission_passport(
        passport,
        artifact_store=artifact_store,
        authority=authority,
    )


def _owner_cache_fence(
    repo_root: Path,
    *,
    catalog_path: Path,
    l5_path: Path,
) -> str:
    n10_path = repo_root / DEFAULT_N10_CAPSTONE
    n13b_path = repo_root / DEFAULT_N13B_CONTRACT
    n10_payload = _read_json_mapping(n10_path, owner="n10_capstone_cache_fence")
    n13b_payload = _read_json_mapping(n13b_path, owner="n13b_contract_cache_fence")
    records: list[tuple[str, str]] = [
        ("catalog", _file_sha256(catalog_path)),
        ("l5", _file_sha256(l5_path)),
        (DEFAULT_N10_CAPSTONE.as_posix(), _file_sha256(n10_path)),
        (DEFAULT_N13B_CONTRACT.as_posix(), _file_sha256(n13b_path)),
    ]
    records.extend(_n10_declared_source_fence(repo_root, n10_payload))
    try:
        from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
            extract_route_projection,
        )

        route_projection = extract_route_projection(
            capstone=n10_payload,
            capstone_source=DEFAULT_N10_CAPSTONE.as_posix(),
        )
        records.append(
            (
                "n10_route_projection",
                route_projection.projection_binding.projection_content_sha256,
            )
        )
    except Exception as exc:  # noqa: BLE001 - loader will emit the typed owner error
        records.append(("n10_route_projection", f"invalid:{type(exc).__name__}"))

    for key in (
        "authority_owner",
        "journal",
        "quarantine",
        "reentry",
        "world_growth",
        "capstone_routes",
    ):
        nested = n13b_payload.get(key)
        projection_hash = nested.get("projection_sha256") if isinstance(nested, dict) else None
        records.append((f"n13b_{key}_projection", str(projection_hash or "missing")))

    registry_path = repo_root / DEFAULT_N13B_REGISTRY
    registry_payload = _read_json_mapping(registry_path, owner="n13b_registry_cache_fence")
    records.extend(
        (
            ("n13b_registry_content", str(registry_payload.get("content_sha256") or "missing")),
            (DEFAULT_N13B_REGISTRY.as_posix(), _file_sha256(registry_path)),
        )
    )
    declared_paths: set[str] = {
        DEFAULT_N13B_JOURNAL.as_posix(),
        DEFAULT_N13B_REENTRY_TRACE.as_posix(),
        DEFAULT_GENERATED_ARTIFACTS.as_posix(),
    }
    for field in ("source_owners", "evidence_bindings"):
        raw_rows = n13b_payload.get(field)
        if not isinstance(raw_rows, list):
            records.append((f"n13b_{field}", "invalid"))
            continue
        for raw_row in raw_rows:
            if isinstance(raw_row, dict) and isinstance(raw_row.get("path"), str):
                declared_paths.add(str(raw_row["path"]))
            else:
                records.append((f"n13b_{field}_row", "invalid"))
    for relative in sorted(declared_paths):
        path = _resolve_relative_owner_path(repo_root, relative)
        records.append((relative, _file_sha256_or_missing(path)))
    records.extend(_directory_fence(repo_root / DEFAULT_N13B_CAS, repo_root=repo_root))
    overlay_ref = _overlay_ref_from_reentry(repo_root)
    overlay_path = _resolve_repo_ref(repo_root, overlay_ref)
    records.append((overlay_ref, _file_sha256_or_missing(overlay_path)))
    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _n10_declared_source_fence(
    repo_root: Path,
    n10_payload: Mapping[str, Any],
) -> tuple[tuple[str, str], ...]:
    """Hash every source reference declared by the N10 owner.

    The source vocabulary is data-derived: a newly declared owner path enters
    the fence without a checker-code change.  Literal content identities are
    retained as identities rather than misread as paths.
    """

    top_level = n10_payload.get("source_refs")
    stability = n10_payload.get("provenance_stability")
    nested = stability.get("source_refs") if isinstance(stability, dict) else None
    if not isinstance(top_level, dict) or not isinstance(nested, dict):
        raise OwnerProjectionError("n10_source_refs_missing")
    if top_level != nested:
        raise OwnerProjectionError("n10_source_refs_projection_drift")
    records: list[tuple[str, str]] = []
    for key, raw_ref in sorted(top_level.items()):
        if type(key) is not str or type(raw_ref) is not str:
            raise OwnerProjectionError("n10_source_ref_invalid")
        record_key = f"n10_source_ref:{key}"
        if raw_ref.startswith("sha256:"):
            if len(raw_ref) != 71 or any(char not in "0123456789abcdef" for char in raw_ref[7:]):
                raise OwnerProjectionError("n10_source_identity_invalid", key)
            records.append((record_key, raw_ref))
            continue
        path = (
            _resolve_repo_ref(repo_root, raw_ref)
            if raw_ref.startswith("repo://")
            else _resolve_relative_owner_path(repo_root, raw_ref)
        )
        records.append((record_key, _file_sha256(path)))
    return tuple(records)


def _strict_db_int(value: object, *, field: str) -> int:
    """Accept an exact database integer without bool/string coercion."""

    if type(value) is not int:
        raise OwnerProjectionError("n13b_overlay_row_wire_invalid", field)
    return value


def _overlay_ref_from_reentry(repo_root: Path) -> str:
    payload = _read_json_mapping(
        Path(repo_root) / DEFAULT_N13B_REENTRY_TRACE,
        owner="n13b_reentry_cache_fence",
    )
    state = payload.get("overlay_state")
    if not isinstance(state, dict) or not isinstance(state.get("overlay_ref"), str):
        raise OwnerProjectionError("n13b_overlay_ref_missing")
    return str(state["overlay_ref"])


def _directory_fence(directory: Path, *, repo_root: Path) -> tuple[tuple[str, str], ...]:
    if not directory.exists():
        return ((directory.relative_to(repo_root).as_posix(), "missing"),)
    if not directory.is_dir():
        raise OwnerProjectionError("n13b_cas_owner_invalid")
    rows: list[tuple[str, str]] = []
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        rows.append((path.relative_to(repo_root).as_posix(), _file_sha256(path)))
    return tuple(rows)


def _resolve_repo_ref(repo_root: Path, ref: str) -> Path:
    prefix = "repo://"
    if not ref.startswith(prefix):
        raise OwnerProjectionError("owner_repo_ref_invalid", ref)
    return _resolve_relative_owner_path(repo_root, ref.removeprefix(prefix))


def _resolve_relative_owner_path(repo_root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        raise OwnerProjectionError("owner_path_outside_repo", relative)
    root = Path(repo_root).resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise OwnerProjectionError("owner_path_outside_repo", relative) from exc
    return candidate


def _read_json_mapping(path: Path, *, owner: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerProjectionError(f"{owner}_unreadable", str(exc)) from exc
    if not isinstance(payload, dict):
        raise OwnerProjectionError(f"{owner}_mapping_required")
    return payload


def _content_sha256(value: object) -> str:
    from polisyos.fabric.data_plane import content_sha256

    return content_sha256(value)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise OwnerProjectionError("owner_file_unreadable", str(path)) from exc
    return f"sha256:{digest.hexdigest()}"


def _file_sha256_or_missing(path: Path) -> str:
    if not path.is_file():
        return "missing"
    return _file_sha256(path)


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


load_owner_bundle.cache_clear = clear_owner_bundle_cache  # type: ignore[attr-defined]


__all__ = [
    "DEFAULT_N10_CAPSTONE",
    "N10OwnerProjection",
    "N10RouteOwnerProjection",
    "N13bAttemptOwnerProjection",
    "N13bOwnerProjection",
    "N13bPassportOwnerProjection",
    "OwnerEvidenceBundle",
    "OwnerProjectionError",
    "clear_owner_bundle_cache",
    "load_owner_bundle",
    "owner_bundle_cache_stats",
]
