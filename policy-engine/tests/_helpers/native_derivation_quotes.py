"""Adopt explicit test quote inputs for already recorded native N7 leaves."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from polisyos.core import artifacts, canon
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality import acquisition_planner as acquisition_planner_owner
from polisyos.runtime.quality.acquisition_planner import (
    NativeDerivationLeafCostProfile,
    NativeDerivationLeafCostProfileScope,
    persist_native_derivation_leaf_cost_profile,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    NativeDerivationLeafProviderSelection,
    NativeDerivationLeafRouteAvailability,
    VerifiedAcquisitionRouteClosure,
)
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthConfig,
    NativeDerivationRouteConfiguration,
)


def _scope_wire(scope: NativeDerivationLeafCostProfileScope) -> dict[str, Any]:
    """Return the actual expected leaf scope with selected refs retained."""
    return scope.model_dump(mode="json")


def _quote_artifact(
    store: Any,
    scope: NativeDerivationLeafCostProfileScope,
    *,
    amount_usd: float,
    effective_at: datetime,
    expires_at: datetime,
) -> artifacts.ArtifactRef:
    """Persist one selected fixture quote whose body repeats its exact scope."""
    line_item_id = "selected_leaf_request"
    payload = {
        "schema_version": "polisyos.tests.native_derivation_leaf_quote.v1",
        "fixture_status": "demonstrative_external_quote_input",
        "authority_purpose": "candidate_cost_provenance_only",
        "scope": _scope_wire(scope),
        "currency": "USD",
        "effective_at": effective_at.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "line_items": [
            {
                "line_item_id": line_item_id,
                "quantity": 1.0,
                "quantity_unit": "selected leaf request",
                "rate_usd": amount_usd,
                "amount_usd": amount_usd,
            }
        ],
        "limitations": [
            "controlled_test_quote_not_provider_invoice",
            "does_not_assert_source_truth_or_currentness",
            "does_not_grant_acquisition_permission",
        ],
    }
    spec = canon.CanonSpec(forbid_floats=False, forbid_nan_inf=True)
    inputs = [
        artifacts.input_ref_from_artifact_ref(ref, role=role)
        for ref, role in (
            (scope.configured_port_source_ref, "selected_configured_port_source"),
            (scope.planner_report_ref, "selected_planner_report"),
            (scope.derivation_bundle_ref, "selected_derivation_bundle"),
            (scope.obligation_set_ref, "selected_obligation_set"),
            (scope.selected_supplier_ref, "selected_source_supplier"),
        )
    ]
    ref = store.put_json(
        payload,
        artifacts.PutOptions(
            kind="external.owner_quote_fact",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="polisyos.tests.NativeDerivationLeafQuote", version="1.0"
            ),
            producer=artifacts.ProducerInfo(
                component="tests.native_derivation_quotes", version="1.0"
            ),
            canon=artifacts.CanonInfo.from_spec(spec),
            inputs=inputs,
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )
    if (
        type(ref) is not artifacts.ArtifactRef
        or ref.kind != "external.owner_quote_fact"
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
    ):
        raise ValueError("native_derivation_fixture_quote_not_selected")
    return ref


def _profile_for_scope(
    store: Any,
    scope: NativeDerivationLeafCostProfileScope,
    *,
    amount_usd: float,
    now: datetime,
) -> artifacts.ArtifactRef:
    """Persist one cost profile from this leaf's own explicit quote amount."""
    effective_at = now - timedelta(minutes=1)
    expires_at = now + timedelta(hours=1)
    quote_ref = _quote_artifact(
        store,
        scope,
        amount_usd=amount_usd,
        effective_at=effective_at,
        expires_at=expires_at,
    )
    line_item_id = "selected_leaf_request"
    payload = {
        "schema_version": "polisyos.runtime.native_derivation_leaf_cost_profile.v1",
        "authority_purpose": "costing_and_provenance_only",
        "scope": _scope_wire(scope),
        "quote_evidence_ref": quote_ref.model_dump(mode="json"),
        "effective_at": effective_at.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "rule_version": "test.external-native-quote.v1",
        "collection_mode": "demonstrative selected fixture quote",
        "currency": "USD",
        "line_items": [
            {
                "line_item_id": line_item_id,
                "quantity": 1.0,
                "rate_name": "explicit_test_quote_usd",
                "unit_rate": amount_usd,
                "amount": amount_usd,
            }
        ],
        "quantity_unit_by_line_item": {line_item_id: "selected leaf request"},
        "calendar_days": 0,
        "expert_hours": 0.0,
    }
    profile = NativeDerivationLeafCostProfile.model_validate(
        {
            **payload,
            "content_hash": acquisition_planner_owner._stable_content_hash(payload),
        }
    )
    return persist_native_derivation_leaf_cost_profile(store, profile)


def adopt_served_native_leaf_quotes(
    served_case: Any,
    holder: dict[str, Any],
    *,
    quote_usd_by_node: Mapping[str, float],
) -> tuple[VerifiedAcquisitionRouteClosure, ...]:
    """Adopt one explicit selected test quote for every real pending native leaf.

    The source actor, configured source, leaf scopes, and provider selections are
    reopened from the served owners. Quote amounts are explicit fixture inputs;
    this helper does not fetch data, authorize an action, or claim empirical truth.
    """
    claims = served_case.claims
    container = served_case.client.app.state.runtime_container
    action_service = container.acquisition_action_service
    control_service = container.control_service
    run_id = served_case.control_run_id
    if not isinstance(quote_usd_by_node, Mapping):
        raise TypeError("native_derivation_quote_map_untyped")

    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        route_loop = action_service._route_loop(
            tenant_id=claims.tenant_id,
            cell_id=claims.cell_id,
        )
        pending = route_loop.resolve_native_derivation_leaf_routes(run_id=run_id)

    if not pending or any(
        type(row) is not NativeDerivationLeafRouteAvailability for row in pending
    ):
        raise ValueError("native_derivation_real_leaf_scope_unavailable")
    scopes_by_node: dict[str, NativeDerivationLeafCostProfileScope] = {}
    for row in pending:
        scope = row.expected_scope
        if type(scope) is not NativeDerivationLeafCostProfileScope:
            raise ValueError("native_derivation_real_leaf_expected_scope_missing")
        if row.source_node_id != scope.source_node_id or scope.source_node_id in scopes_by_node:
            raise ValueError("native_derivation_real_leaf_scope_denominator_invalid")
        if (
            scope.tenant_id != claims.tenant_id
            or scope.cell_id != claims.cell_id
            or scope.run_id != run_id
        ):
            raise ValueError("native_derivation_real_leaf_actor_scope_mismatch")
        scopes_by_node[scope.source_node_id] = scope

    node_ids = tuple(scopes_by_node)
    if any(type(node_id) is not str for node_id in quote_usd_by_node) or set(
        quote_usd_by_node
    ) != set(node_ids):
        raise ValueError("native_derivation_quote_map_leaf_denominator_mismatch")
    amounts_by_node: dict[str, float] = {}
    for node_id, amount in quote_usd_by_node.items():
        if isinstance(amount, bool) or not isinstance(amount, int | float):
            raise ValueError("native_derivation_quote_amount_invalid")
        try:
            amount_usd = float(amount)
        except (OverflowError, ValueError) as exc:
            raise ValueError("native_derivation_quote_amount_invalid") from exc
        if not math.isfinite(amount_usd) or amount_usd <= 0.0:
            raise ValueError("native_derivation_quote_amount_invalid")
        amounts_by_node[node_id] = amount_usd

    first_scope = scopes_by_node[node_ids[0]]
    source_ref_key = artifacts.artifact_ref_identity_key(first_scope.configured_port_source_ref)
    source_actor = (
        first_scope.tenant_id,
        first_scope.cell_id,
        first_scope.run_id,
        first_scope.source_job_id,
    )
    if any(
        (
            scope.tenant_id,
            scope.cell_id,
            scope.run_id,
            scope.source_job_id,
        )
        != source_actor
        or artifacts.artifact_ref_identity_key(scope.configured_port_source_ref) != source_ref_key
        for scope in scopes_by_node.values()
    ):
        raise ValueError("native_derivation_leaf_sources_not_one_served_origin")

    providers_by_node: dict[str, NativeDerivationLeafProviderSelection] = {}
    for row in holder["rows"]:
        provider = row.get("provider")
        if type(provider) is not NativeDerivationLeafProviderSelection:
            raise ValueError("native_derivation_holder_provider_untyped")
        node_id = provider.source_node_id
        scope = scopes_by_node.get(node_id)
        if (
            scope is None
            or node_id in providers_by_node
            or artifacts.artifact_ref_identity_key(provider.supplier_ref)
            != artifacts.artifact_ref_identity_key(scope.selected_supplier_ref)
        ):
            raise ValueError("native_derivation_holder_provider_scope_mismatch")
        providers_by_node[node_id] = provider
    if set(providers_by_node) != set(scopes_by_node):
        raise ValueError("native_derivation_holder_provider_denominator_mismatch")

    configuration = holder.get("configuration")
    if type(configuration) is not AcquisitionWorldGrowthConfig:
        raise TypeError("native_derivation_holder_configuration_untyped")
    if any(row.key == source_actor for row in configuration.native_derivation_routes):
        raise ValueError("native_derivation_leaf_quotes_already_adopted")

    store = control_service._artifact_store
    now = datetime.now(UTC)
    profile_refs_by_node: dict[str, artifacts.ArtifactRef] = {}
    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        for node_id in node_ids:
            amount = amounts_by_node[node_id]
            profile_refs_by_node[node_id] = _profile_for_scope(
                store,
                scopes_by_node[node_id],
                amount_usd=amount,
                now=now,
            )

    native_route = NativeDerivationRouteConfiguration(
        tenant_id=source_actor[0],
        cell_id=source_actor[1],
        run_id=source_actor[2],
        source_job_id=source_actor[3],
        configured_port_source_ref=first_scope.configured_port_source_ref,
        owner_declared_cost_profile_refs=tuple(
            profile_refs_by_node[node_id] for node_id in node_ids
        ),
        supplier_selections=tuple(providers_by_node[node_id] for node_id in node_ids),
    )
    config_payload = configuration.model_dump(mode="python")
    config_payload["native_derivation_routes"] = (
        *configuration.native_derivation_routes,
        native_route,
    )
    adopted_configuration = AcquisitionWorldGrowthConfig.model_validate(config_payload)
    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        control_service.bind_native_derivation_route_configuration(adopted_configuration)
    holder["configuration"] = adopted_configuration

    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        resolved = action_service._route_loop(
            tenant_id=claims.tenant_id,
            cell_id=claims.cell_id,
        ).resolve_native_derivation_leaf_routes(run_id=run_id)
    if len(resolved) != len(node_ids) or any(
        type(row) is not VerifiedAcquisitionRouteClosure for row in resolved
    ):
        raise ValueError("native_derivation_costed_leaf_routes_unresolved")
    closures_by_node: dict[str, VerifiedAcquisitionRouteClosure] = {}
    for closure in resolved:
        scope = closure.native_derivation_leaf_scope
        if type(scope) is not NativeDerivationLeafCostProfileScope:
            raise ValueError("native_derivation_costed_leaf_scope_missing")
        node_id = scope.source_node_id
        if (
            node_id not in scopes_by_node
            or node_id in closures_by_node
            or _scope_wire(scope) != _scope_wire(scopes_by_node[node_id])
            or closure.owner_declared_profile_ref is None
            or artifacts.artifact_ref_identity_key(closure.owner_declared_profile_ref)
            != artifacts.artifact_ref_identity_key(profile_refs_by_node[node_id])
        ):
            raise ValueError("native_derivation_costed_leaf_route_mismatch")
        provider = closure.native_derivation_leaf_provider
        expected_provider = providers_by_node[node_id]
        if type(provider) is not NativeDerivationLeafProviderSelection or provider.model_dump(
            mode="json"
        ) != expected_provider.model_dump(mode="json"):
            raise ValueError("native_derivation_costed_leaf_provider_mismatch")
        closures_by_node[node_id] = closure
    if set(closures_by_node) != set(scopes_by_node):
        raise ValueError("native_derivation_costed_leaf_denominator_mismatch")
    return tuple(closures_by_node[node_id] for node_id in node_ids)
