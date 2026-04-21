"""Evaluate proxy, transport, strategic-response, and counterfactual readiness IR bundles.

These runners consume typed C4a observation bundles and a reconciled
`CausalGraphModel`, call Foundry identification/transport/strategic methods, and
emit normalized readiness entries that `RunCausalReadinessNode` stores in
`CausalReadinessBundle`.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from polisyos.foundry.methods.catalog.causal.id_engine import (
    CtfQuery,
    IdentificationStatus,
    id_star_algorithm,
    idc_star_algorithm,
    tr_algorithm,
)
from polisyos.foundry.methods.catalog.causal.measurement_error import identify_with_proxy
from polisyos.foundry.methods.catalog.causal.strategic import (
    solve_strategic_response,
    strategic_result_summary,
)
from polisyos.ir.analytics.abstraction import AbstractionCertificate
from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.privacy_transportability import (
    DPUtilityManifest,
    PrivacyObservedMode,
    TransportPrivacyContext,
    apply_transport_privacy_context,
    coerce_dp_utility_manifest,
)
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    StrategicSCM,
    persist_strategic_payoff_table,
    persist_strategic_scm,
    persist_strategic_solve_artifacts,
)
from polisyos.ir.analytics.transportability import (
    SelectionDiagram,
    SNode,
    SNodeOrigin,
    SNodeRole,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
    persist_transportability_result,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.observation.bundles import (
    CounterfactualCheckBundle,
    InterferenceLossSpecBundle,
    ProxyIdentificationBundle,
    StrategicResponseSpecsBundle,
    TransportabilityCheckBundle,
)
from polisyos.ir.observation.causal_readiness import (
    CounterfactualCheckEntry,
    InterferenceReadinessEntry,
    ProxyIdentificationEntry,
    StrategicResponseEntry,
    TransportabilityCheckEntry,
)
from polisyos.ir.observation.governance import ObservationFamilyPolicyRegistry
from polisyos.ir.observation.measurement import (
    RegimeCalendar,
    SchemaRegimeRegistry,
    ShockCalendar,
)
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.error_semantics import emit_degraded_path


def _artifact_input_ref(ref: ArtifactRefModel | None, *, role: str) -> InputRef | None:
    if ref is None:
        return None
    return InputRef(artifact_id=ref.artifact_id, role=role)


def _normalize_reason(*, status: str, trace: list[str], default: str) -> str:
    for item in reversed(trace):
        token = str(item).strip()
        if token:
            return token[:255]
    return f"{status}:{default}"[:255]


def _proof_steps_payload(proof_steps: list[Any]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for step in proof_steps:
        try:
            payload.append(asdict(step))
        except TypeError:
            payload.append({"value": str(step)})
    return payload


def _coerce_context(payload: Any) -> ContextProfile:
    if payload is None:
        return ContextProfile()
    if isinstance(payload, ContextProfile):
        return payload
    return ContextProfile.model_validate(payload)


def _privacy_s_nodes_from_manifest(manifest: DPUtilityManifest) -> list[SNode]:
    nodes: list[SNode] = []
    for variable in manifest.privacy_mismatch_variables:
        nodes.append(
            SNode(
                target_variable=variable,
                context_dimension="privacy_scope_mismatch",
                source_value="private_scope_mismatch",
                target_value="private_scope_mismatch",
                delta=1.0,
                severity="high",
                origin=SNodeOrigin.PRIVACY,
                role=SNodeRole.PRE_TREATMENT_COVARIATE,
            )
        )
    return nodes


def _transport_entry_status(
    result_model: TransportabilityResult,
    privacy_mode: PrivacyObservedMode | None,
) -> str:
    if result_model.status is TransportabilityStatus.UNSUPPORTED:
        return "blocked"
    if privacy_mode in {PrivacyObservedMode.INTERVAL, PrivacyObservedMode.BOUNDS_ONLY}:
        return "partially_identified"
    if privacy_mode is PrivacyObservedMode.BLOCKED:
        return "blocked"
    return result_model.status.value


def _coerce_payoff_tables(payload: Any) -> dict[str, FiniteStrategicPayoffTable]:
    if not isinstance(payload, Mapping) or not payload:
        raise ValueError("strategic_payoff_tables must be a non-empty mapping")
    return {
        str(agent): (
            table if isinstance(table, FiniteStrategicPayoffTable) else FiniteStrategicPayoffTable.model_validate(table)
        )
        for agent, table in payload.items()
    }


def _coerce_counterfactual_query(payload: Any) -> CtfQuery:
    if isinstance(payload, CtfQuery):
        return payload
    if not isinstance(payload, Mapping):
        raise ValueError("counterfactual query must be a mapping")

    def _tuple_mapping(value: Any) -> tuple[tuple[str, float], ...]:
        if value in (None, (), []):
            return ()
        if isinstance(value, Mapping):
            return tuple((str(key), float(raw)) for key, raw in value.items())
        if isinstance(value, (list, tuple)):
            result: list[tuple[str, float]] = []
            for item in value:
                if isinstance(item, Mapping):
                    result.append((str(item["name"]), float(item["value"])))
                else:
                    key, raw = item
                    result.append((str(key), float(raw)))
            return tuple(result)
        raise ValueError("counterfactual assignments must be a mapping or sequence")

    return CtfQuery(
        outcome=str(payload["outcome"]),
        intervention=_tuple_mapping(payload.get("intervention")),
        conditioning=tuple(str(item) for item in payload.get("conditioning", ())),
        evidence=_tuple_mapping(payload.get("evidence")),
        kind=str(payload.get("kind", "generic")),
        mediators=tuple(str(item) for item in payload.get("mediators", ())),
        protected_attribute=(
            None if payload.get("protected_attribute") is None else str(payload.get("protected_attribute"))
        ),
        reference_intervention=_tuple_mapping(payload.get("reference_intervention")),
        outcome_value=(
            None if payload.get("outcome_value") is None else float(payload.get("outcome_value"))
        ),
    )


def _cross_regime_boundary_s_nodes(
    *,
    check: Any,
    outcome: str,
    regime_calendar: RegimeCalendar | None,
    schema_regime_registry: SchemaRegimeRegistry | None,
    shock_calendar: ShockCalendar | None,
) -> list[SNode]:
    if not check.period_start or not check.period_end or check.time_grain is None:
        return []
    synthesized: list[SNode] = []
    if regime_calendar is not None and regime_calendar.is_boundary(
        regime_id=check.target_regime_id or check.source_regime_id,
        period_start=check.period_start,
        period_end=check.period_end,
        time_grain=check.time_grain,
    ):
        synthesized.append(
            SNode(
                target_variable=outcome,
                context_dimension="regime_boundary",
                source_value=str(check.source_regime_id or ""),
                target_value=str(check.target_regime_id or ""),
                delta=1.0,
                severity="high",
                origin=SNodeOrigin.DATA_MISMATCH,
            )
        )
    if (
        schema_regime_registry is not None
        and check.schema_regime_id is not None
        and schema_regime_registry.is_boundary(
            schema_regime_id=check.schema_regime_id,
            period_start=check.period_start,
            period_end=check.period_end,
            time_grain=check.time_grain,
        )
    ):
        synthesized.append(
            SNode(
                target_variable=outcome,
                context_dimension="schema_boundary",
                source_value=str(check.schema_regime_id),
                target_value=str(check.schema_regime_id),
                delta=1.0,
                severity="high",
                origin=SNodeOrigin.DATA_MISMATCH,
            )
        )
    if shock_calendar is not None and shock_calendar.is_boundary(
        period_start=check.period_start,
        period_end=check.period_end,
        time_grain=check.time_grain,
        regime_id=check.target_regime_id or check.source_regime_id,
    ):
        synthesized.append(
            SNode(
                target_variable=outcome,
                context_dimension="shock_boundary",
                source_value=0.0,
                target_value=1.0,
                delta=1.0,
                severity="high",
                origin=SNodeOrigin.DATA_MISMATCH,
            )
        )
    return synthesized


class ProxyIdentificationRunner:
    """Score each proxy channel against the reconciled graph via Foundry proxy-ID logic.

    Use this runner when a `ProxyIdentificationBundle` has already been built by
    observation-layer code and you need normalized `ProxyIdentificationEntry`
    rows for governance. Family-specific measurement-model names may be injected
    from workflow state to keep the output traceable.
    """

    def __init__(
        self,
        *,
        graph: CausalGraphModel,
        policy_registry: ObservationFamilyPolicyRegistry | None = None,
    ) -> None:
        self.graph = graph
        self.policy_registry = policy_registry or ObservationFamilyPolicyRegistry.default()

    def run(
        self,
        bundle: ProxyIdentificationBundle | None,
        *,
        measurement_models: Mapping[str, str] | None = None,
    ) -> list[ProxyIdentificationEntry]:
        """Evaluate each proxy-identification channel in the supplied bundle.

        Args:
            bundle: Proxy-readiness input bundle; `None` yields no entries.
            measurement_models: Optional family-to-model mapping used by
                `identify_with_proxy()`.

        Returns:
            One `ProxyIdentificationEntry` per channel with status, estimand,
            proof trace, and normalized blocker reason when oracle support is
            still required.
        """

        if bundle is None:
            return []
        models = dict(measurement_models or {})
        entries: list[ProxyIdentificationEntry] = []
        for channel in bundle.proxy_channels:
            result = identify_with_proxy(
                self.graph,
                treatment=channel.treatment_variable or channel.proxy_variable,
                outcome=channel.outcome_variable or channel.latent_variable,
                proxy_map={channel.latent_variable: channel.proxy_variable},
                measurement_model=models.get(channel.family.value, "unknown"),
            )
            status = (
                "identified"
                if result.status is IdentificationStatus.IDENTIFIED
                else "oracle_needed"
            )
            entries.append(
                ProxyIdentificationEntry(
                    family=channel.family,
                    proxy_variable=channel.proxy_variable,
                    latent_variable=channel.latent_variable,
                    status=status,
                    verification_method=channel.verification_method,
                    measurement_model=models.get(channel.family.value, "unknown"),
                    estimand_ast=(
                        None
                        if result.estimand_ast is None
                        else result.estimand_ast.model_dump(mode="json")
                    ),
                    proof_steps=_proof_steps_payload(result.proof_steps),
                    trace=list(result.trace),
                    normalized_reason=(
                        None
                        if status == "identified"
                        else _normalize_reason(
                            status=result.status.value,
                            trace=list(result.trace),
                            default="proxy_identification_blocked",
                        )
                    ),
                    metadata={"algorithm_version": result.algorithm_version},
                )
            )
        return entries


class TransportabilityChecker:
    """Check whether requested effects transport from source to target contexts.

    Explicit `SNode` annotations from the IR bundle are merged with synthesized
    mismatch nodes from regime/schema/shock calendars before calling Foundry's
    `tr_algorithm()`. A persisted `TransportabilityResult` ref is attached to
    each returned entry so governance passes can audit why transport succeeded or
    failed.
    """

    def __init__(
        self,
        *,
        graph: CausalGraphModel,
        store: Any,
        base_inputs: list[InputRef] | None = None,
    ) -> None:
        self.graph = graph
        self.store = store
        self.base_inputs = list(base_inputs or [])

    def run(
        self,
        bundle: TransportabilityCheckBundle | None,
        *,
        regime_calendar: RegimeCalendar | None = None,
        schema_regime_registry: SchemaRegimeRegistry | None = None,
        shock_calendar: ShockCalendar | None = None,
    ) -> list[TransportabilityCheckEntry]:
        """Run all transportability checks and persist one result artifact per check."""

        if bundle is None:
            return []
        entries: list[TransportabilityCheckEntry] = []
        for check in bundle.checks:
            source_context = _coerce_context(check.source_context)
            target_context = _coerce_context(check.target_context)
            dp_utility_manifest = coerce_dp_utility_manifest(getattr(check, "dp_utility_manifest", None))
            synthesized = _cross_regime_boundary_s_nodes(
                check=check,
                outcome=check.outcome,
                regime_calendar=regime_calendar,
                schema_regime_registry=schema_regime_registry,
                shock_calendar=shock_calendar,
            )
            privacy_s_nodes = (
                _privacy_s_nodes_from_manifest(dp_utility_manifest)
                if dp_utility_manifest is not None
                else []
            )
            s_nodes = [*list(check.explicit_s_nodes), *synthesized, *privacy_s_nodes]
            same_regime = (
                check.source_regime_id is not None
                and check.source_regime_id == check.target_regime_id
                and not s_nodes
            )
            query = f"P({check.outcome}|do({check.treatment}))"
            if same_regime:
                result_model = TransportabilityResult(
                    query=query,
                    status=TransportabilityStatus.IDENTIFIED,
                        transport_mode=TransportMode.DIRECT,
                        identification_engine="same_regime_short_circuit",
                        identification_trace=["same_regime_short_circuit"],
                        selection_diagram_ref=f"selection_diagram:{check.check_id}:same_regime",
                        source_context_id=source_context.context_id,
                        target_context_id=target_context.context_id,
                        metadata={"check_id": check.check_id, "cross_regime": False},
                    )
            else:
                selection_diagram = SelectionDiagram(
                    base_graph=self.graph,
                    s_nodes=s_nodes,
                    source_context=source_context,
                    target_context=target_context,
                    context_distance=source_context.distance_to(target_context),
                )
                selection_diagram_ref = f"selection_diagram:{check.check_id}"
                result = tr_algorithm(
                    treatment=frozenset({check.treatment}),
                    outcome=frozenset({check.outcome}),
                    selection_diagram=selection_diagram,
                )
                if result.status is IdentificationStatus.IDENTIFIED:
                    result_model = TransportabilityResult(
                        query=query,
                        status=TransportabilityStatus.IDENTIFIED,
                        transport_mode=TransportMode.DIRECT,
                        blocking_s_nodes=[],
                        identification_engine=result.algorithm_version,
                        identification_trace=list(result.trace),
                        selection_diagram_ref=selection_diagram_ref,
                        source_context_id=source_context.context_id,
                        target_context_id=target_context.context_id,
                        estimand_ast=(
                            None
                            if result.estimand_ast is None
                            else result.estimand_ast.model_dump(mode="json")
                        ),
                        metadata={"check_id": check.check_id, "cross_regime": True},
                    )
                else:
                    blocking_nodes = [
                        node
                        for node in s_nodes
                        if not result.hedge_certificate
                        or not result.hedge_certificate.minimal_required_s_nodes
                        or f"S_{node.target_variable}" in result.hedge_certificate.minimal_required_s_nodes
                    ]
                    result_model = TransportabilityResult(
                        query=query,
                        status=TransportabilityStatus.UNSUPPORTED,
                        transport_mode=TransportMode.NONE,
                        blocking_s_nodes=blocking_nodes,
                        identification_engine=result.algorithm_version,
                        identification_trace=list(result.trace),
                        selection_diagram_ref=selection_diagram_ref,
                        unsupported_reason=_normalize_reason(
                            status=result.status.value,
                            trace=list(result.trace),
                            default="transportability_blocked",
                        ),
                        source_context_id=source_context.context_id,
                        target_context_id=target_context.context_id,
                        metadata={"check_id": check.check_id, "cross_regime": True},
                    )
            privacy_mode: PrivacyObservedMode | None = None
            if dp_utility_manifest is not None:
                result_model = apply_transport_privacy_context(
                    result_model,
                    TransportPrivacyContext(
                        utility_manifest=dp_utility_manifest,
                        store=self.store,
                        inputs=tuple(self.base_inputs),
                        certificate_id=f"{check.check_id}_privacy_transport",
                        selection_diagram_ref=(
                            result_model.selection_diagram_ref
                            or f"selection_diagram:{check.check_id}"
                        ),
                    ),
                )
                privacy_mode_raw = result_model.metadata.get("privacy_observed_mode")
                if isinstance(privacy_mode_raw, str):
                    privacy_mode = PrivacyObservedMode(privacy_mode_raw)
            result_ref = persist_transportability_result(
                self.store,
                result_model,
                inputs=self.base_inputs,
            )
            entries.append(
                TransportabilityCheckEntry(
                    check_id=check.check_id,
                    family=check.family,
                    status=_transport_entry_status(result_model, privacy_mode),
                    cross_regime=not same_regime,
                    result_ref=ArtifactRefModel.model_validate(result_ref.model_dump(mode="json")),
                    blocking_s_nodes=[node.target_variable for node in result_model.blocking_s_nodes],
                    identification_engine=result_model.identification_engine,
                    normalized_reason=result_model.unsupported_reason,
                    trace=list(result_model.identification_trace),
                    metadata=dict(result_model.metadata),
                )
            )
        return entries


class StrategicResponseRunner:
    """Solve strategic-response contracts and produce readiness entries per channel.

    The runner validates channel payloads from workflow state, persists payoff
    tables and the normalized `StrategicSCM`, executes Foundry's strategic solver,
    and materializes readiness entries plus `StrategicResponseBundle` refs that
    `StrategicResponsePass` later validates.
    """

    def __init__(
        self,
        *,
        store: Any,
        causal_component_ref: ArtifactRefModel,
        base_inputs: list[InputRef] | None = None,
        run_metadata: dict[str, Any] | None = None,
    ) -> None:
        self.store = store
        self.causal_component_ref = causal_component_ref
        self.base_inputs = list(base_inputs or [])
        self.run_metadata = dict(run_metadata or {})

    def _persist_tables(
        self,
        tables: Mapping[str, FiniteStrategicPayoffTable],
    ) -> dict[str, ArtifactRefModel]:
        refs: dict[str, ArtifactRefModel] = {}
        for agent, table in tables.items():
            ref = persist_strategic_payoff_table(self.store, table, inputs=self.base_inputs)
            refs[agent] = ArtifactRefModel.model_validate(ref.model_dump(mode="json"))
        return refs

    def _blocked_entry(
        self,
        *,
        channel: str,
        intervention_kind: str | None,
        reason: str,
        summary: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
    ) -> StrategicResponseEntry:
        return StrategicResponseEntry(
            channel=channel,
            intervention_kind=intervention_kind,
            status="blocked",
            fallback_mode="blocked",
            warnings=list(warnings or []),
            blocked_reason=reason,
            summary=dict(summary or {"blocked_reason": reason, "fallback_mode": "blocked"}),
        )

    def run(
        self,
        specs_bundle: StrategicResponseSpecsBundle | None,
        *,
        channel_payloads: Mapping[str, Any] | None = None,
    ) -> list[StrategicResponseEntry]:
        """Evaluate strategic-response readiness for all expected channels.

        Args:
            specs_bundle: Expected-channel contract from observation-layer IR.
            channel_payloads: Runtime payloads keyed by channel name; each payload
                must include `strategic_scm` and `strategic_payoff_tables`.

        Returns:
            One `StrategicResponseEntry` per expected or supplied channel,
            including persisted SCM/bundle refs when solved and normalized
            blocker metadata when inputs are missing or invalid.
        """

        payloads = dict(channel_payloads or {})
        expected_channels: dict[str, str | None] = {}
        if specs_bundle is not None:
            for expectation in specs_bundle.expectations:
                if not expectation.strategic_response_expected:
                    continue
                for channel in expectation.channels:
                    expected_channels.setdefault(channel.value, expectation.intervention_kind)
        for channel in payloads:
            expected_channels.setdefault(str(channel), None)
        entries: list[StrategicResponseEntry] = []
        for channel, intervention_kind in sorted(expected_channels.items()):
            raw_payload = payloads.get(channel)
            if raw_payload is None:
                entries.append(
                    self._blocked_entry(
                        channel=channel,
                        intervention_kind=intervention_kind,
                        reason="missing_strategic_payload",
                    )
                )
                continue
            try:
                params = dict(raw_payload)
                baseline_policy_value = (
                    None
                    if params.get("baseline_policy_value") is None
                    else float(params.get("baseline_policy_value"))
                )
                contract = StrategicSCM.model_validate(params["strategic_scm"])
                payoff_tables = _coerce_payoff_tables(params.get("strategic_payoff_tables"))
                macro_payload = params.get("macro_strategic_payoff_tables")
                macro_tables = None if macro_payload is None else _coerce_payoff_tables(macro_payload)
                abstraction_payload = params.get("abstraction_certificate")
                abstraction_certificate = (
                    None
                    if abstraction_payload is None
                    else AbstractionCertificate.model_validate(abstraction_payload)
                )
                utility_refs = self._persist_tables(payoff_tables)
                macro_utility_refs = None if macro_tables is None else self._persist_tables(macro_tables)
                normalized_contract = contract.model_copy(
                    update={
                        "utility_refs": utility_refs,
                        "macro_utility_refs": macro_utility_refs,
                    }
                )
                strategic_scm_ref = persist_strategic_scm(
                    self.store,
                    normalized_contract,
                    inputs=self.base_inputs,
                )
                result = solve_strategic_response(
                    normalized_contract,
                    payoff_tables,
                    baseline_policy_value=baseline_policy_value,
                    abstraction_certificate=abstraction_certificate,
                    macro_payoff_tables=macro_tables,
                    performative_loop_spec=params.get("performative_loop_spec"),
                    mean_field_inputs=params.get("mean_field_game"),
                )
                bundle, bundle_ref = persist_strategic_solve_artifacts(
                    self.store,
                    causal_component_ref=self.causal_component_ref,
                    result=result,
                    equilibrium_concept=normalized_contract.equilibrium_concept,
                    equilibrium_descriptor=normalized_contract.equilibrium_descriptor,
                    baseline_policy_value=baseline_policy_value,
                    inputs=self.base_inputs,
                    metadata={
                        **self.run_metadata,
                        "channel": channel,
                        "intervention_kind": intervention_kind,
                        "strategic_scm_ref": ArtifactRefModel.model_validate(
                            strategic_scm_ref.model_dump(mode="json")
                        ).model_dump(mode="json"),
                    },
                    mfg_equilibrium_certificate=result.mfg_equilibrium_certificate,
                    mfg_macro_simulation_config=result.mfg_macro_simulation_config,
                    mfg_solver_residual_report=result.mfg_solver_residual_report,
                    mfg_mass_conservation_report=result.mfg_mass_conservation_report,
                )
                summary = strategic_result_summary(result)
                summary.update(
                    {
                        "strategic_response_bundle_ref": bundle_ref.model_dump(mode="json"),
                        "strategic_scm_ref": strategic_scm_ref.model_dump(mode="json"),
                        "mfg_equilibrium_ref": (
                            None
                            if bundle.mfg_equilibrium_ref is None
                            else bundle.mfg_equilibrium_ref.model_dump(mode="json")
                        ),
                    }
                )
                entries.append(
                    StrategicResponseEntry(
                        channel=channel,
                        intervention_kind=intervention_kind,
                        status="ready" if result.blocked_reason is None else "blocked",
                        fallback_mode=result.fallback_mode.value,
                        strategic_scm_ref=ArtifactRefModel.model_validate(
                            strategic_scm_ref.model_dump(mode="json")
                        ),
                        strategic_response_bundle_ref=ArtifactRefModel.model_validate(
                            bundle_ref.model_dump(mode="json")
                        ),
                        performative_shift=result.performative_shift,
                        warnings=[str(item) for item in result.warnings],
                        blocked_reason=result.blocked_reason,
                        summary={
                            **summary,
                            "metadata": dict(bundle.metadata),
                        },
                    )
                )
            except (AttributeError, TypeError, ValueError) as exc:
                envelope = emit_degraded_path(
                    component="causal.readiness",
                    operation="run_strategic_response",
                    reason="strategic_hook_invalid_input",
                    exc=exc,
                    details={
                        "channel": channel,
                        "intervention_kind": intervention_kind,
                    },
                )
                entries.append(
                    self._blocked_entry(
                        channel=channel,
                        intervention_kind=intervention_kind,
                        reason="strategic_hook_invalid_input",
                        summary={
                            "error": str(exc),
                            "error_envelope": envelope,
                            "fallback_mode": "blocked",
                        },
                        warnings=["strategic_hook_invalid_input"],
                    )
                )
        return entries


class CounterfactualQueryRunner:
    """Run ID*/IDC* counterfactual identification checks on the reconciled graph."""

    def __init__(self, *, graph: CausalGraphModel) -> None:
        self.graph = graph

    def run(self, bundle: CounterfactualCheckBundle | None) -> list[CounterfactualCheckEntry]:
        """Evaluate all counterfactual queries contained in a check bundle.

        Args:
            bundle: Counterfactual-readiness bundle; `None` yields no entries.

        Returns:
            One `CounterfactualCheckEntry` per query with normalized
            identification status, optional estimand/proof metadata, and blocker
            reasons suitable for `CounterfactualIdentificationGateNode`.
        """

        if bundle is None:
            return []
        entries: list[CounterfactualCheckEntry] = []
        for item in bundle.queries:
            query = _coerce_counterfactual_query(item.query)
            intervention_map = dict(query.intervention)
            evidence_map = dict(query.evidence)
            conflicting = sorted(
                name
                for name, value in evidence_map.items()
                if name in intervention_map and float(intervention_map[name]) != float(value)
            )
            if conflicting:
                entries.append(
                    CounterfactualCheckEntry(
                        query_id=item.query_id,
                        family=item.family,
                        status=IdentificationStatus.HEDGE_FOUND.value,
                        query_kind=query.kind,
                        algorithm_version="idc_star_v2",
                        normalized_query=str(f"{query.outcome}|{query.kind}")[:500],
                        estimand_ast=None,
                        hedge_certificate=None,
                        trace=[f"counterfactual_conflict:{','.join(conflicting)}"],
                        normalized_reason=(
                            "counterfactual_conflict_between_intervention_and_evidence"
                        ),
                        metadata={"query_kind": query.kind},
                    )
                )
                continue
            result = (
                idc_star_algorithm(query, self.graph)
                if query.evidence
                else id_star_algorithm(query, self.graph)
            )
            entries.append(
                CounterfactualCheckEntry(
                    query_id=item.query_id,
                    family=item.family,
                    status=result.status.value,
                    query_kind=query.kind,
                    algorithm_version=result.algorithm_version,
                    normalized_query=str(result.query_str or f"{query.outcome}|{query.kind}")[:500],
                    estimand_ast=(
                        None
                        if result.estimand_ast is None
                        else result.estimand_ast.model_dump(mode="json")
                    ),
                    hedge_certificate=(
                        None
                        if result.hedge_certificate is None
                        else asdict(result.hedge_certificate)
                    ),
                    trace=list(result.trace),
                    normalized_reason=(
                        None
                        if result.status is IdentificationStatus.IDENTIFIED
                        else _normalize_reason(
                            status=result.status.value,
                            trace=list(result.trace),
                            default="counterfactual_not_identified",
                        )
                    ),
                    metadata={"query_kind": query.kind},
                )
            )
        return entries


def build_interference_readiness_entries(
    bundle: InterferenceLossSpecBundle | None,
) -> list[InterferenceReadinessEntry]:
    """Normalize interference-loss specs into governance-readable readiness entries."""

    if bundle is None:
        return []
    return [
        InterferenceReadinessEntry(
            spec_id=spec.spec_id,
            family=spec.family,
            predicted_metric_path=spec.predicted_metric_path,
            ready=True,
            notes=list(spec.notes),
            metadata={"graph_layer": spec.graph_layer.value, "loss_kind": spec.loss_kind},
        )
        for spec in bundle.specs
    ]


__all__ = [
    "CounterfactualQueryRunner",
    "ProxyIdentificationRunner",
    "StrategicResponseRunner",
    "TransportabilityChecker",
    "build_interference_readiness_entries",
]
