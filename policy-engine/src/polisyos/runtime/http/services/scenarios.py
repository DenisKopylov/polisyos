"""Counterfactual scenario manifests and metrics for runtime surfaces."""

from __future__ import annotations

import json
import math
import re
import threading
from datetime import UTC, datetime
from math import isfinite
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.core import artifacts
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.runtime import (
    CounterfactualMetric,
    LineageCompactSummaryItem,
    LineageExportLinks,
    LineageGraphEdge,
    LineageGraphNode,
    LineageGraphView,
    LineageRef,
    QuantityUncertainty,
    QuantityValue,
    ScenarioAssumption,
    ScenarioCapability,
    ScenarioConstraint,
    ScenarioCreateRequest,
    ScenarioIntervention,
    ScenarioManifest,
    ScenarioRef,
    TemporalRange,
    TemporalRef,
    TemporalScope,
    UnitRef,
)
from polisyos.ir.analytics.phase4_dynamics import (
    Phase4DynamicsGateError,
    Phase4TemporalPolicyGateVerdict,
    validate_phase4_temporal_policy_query,
)
from polisyos.runtime.http.errors import conflict, not_found, service_unavailable

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.runtime.http.services.lineage import LineageService
    from polisyos.runtime.http.services.run_index import IndexedRunRecord
    from polisyos.runtime.http.services.scenario_heads import (
        ScenarioHeadRecord,
        ScenarioHeadStore,
    )
    from polisyos.runtime.http.services.temporal import TemporalService


_SCENARIO_ARTIFACT_KIND = "runtime.scenario_manifest"
_SCENARIO_SCHEMA = SchemaInfo(name="polisyos.runtime.scenario_manifest", version="1")
_SCENARIO_CANON = CanonSpec(forbid_floats=False)


class ScenarioRepository:
    """Durable ScenarioManifest repository backed by the existing CAS ArtifactStore."""

    def __init__(
        self,
        store: ArtifactStore | None,
        *,
        require_durable_heads: bool = False,
    ) -> None:
        self._store = store
        self._head_store: ScenarioHeadStore | None = None
        self._require_durable_heads = require_durable_heads
        self._by_id: dict[str, ScenarioManifest] = {}
        self._artifact_by_id: dict[str, str] = {}
        self._lock = threading.RLock()
        if not require_durable_heads:
            self._hydrate_legacy()

    def bind_head_store(self, head_store: ScenarioHeadStore) -> None:
        """Make one transactional logical-head store authoritative for all revisions."""
        if head_store is None:
            raise TypeError("head_store is required")
        with self._lock:
            if self._head_store is head_store:
                return
            self._head_store = head_store
            self._by_id.clear()
            self._artifact_by_id.clear()
            self._hydrate_heads_locked()

    def get_head(self, scenario_id: str) -> ScenarioHeadRecord | None:
        """Return the current durable logical head without selecting a CAS candidate."""
        with self._lock:
            head_store = self._head_store_or_raise_locked()
            if head_store is None:
                return None
            return head_store.get_scenario_head(scenario_id)

    def get_for_bound_head(self, head: ScenarioHeadRecord) -> ScenarioManifest:
        """Resolve exactly ``head`` and reject a concurrent logical-head change."""
        with self._lock:
            head_store = self._head_store_or_raise_locked()
            if head_store is None:
                raise service_unavailable(
                    "Durable scenario-head authority is unavailable",
                    code="scenario_head_store_unavailable",
                )
            if head_store.get_scenario_head(head.scenario_id) != head:
                raise conflict(
                    "Scenario changed during authorization binding",
                    code="scenario_authorization_binding_changed",
                )
            manifest = self._load_head_locked(head)
            if head_store.get_scenario_head(head.scenario_id) != head:
                raise conflict(
                    "Scenario changed during authorization binding",
                    code="scenario_authorization_binding_changed",
                )
            return manifest

    def get(self, scenario_id: str) -> ScenarioManifest | None:
        """Return a persisted scenario manifest by id, if present."""
        with self._lock:
            head_store = self._head_store_or_raise_locked()
            if head_store is not None:
                head = head_store.get_scenario_head(scenario_id)
                if head is None:
                    self._by_id.pop(scenario_id, None)
                    self._artifact_by_id.pop(scenario_id, None)
                    return None
                return self._load_head_locked(head)
            return self._by_id.get(scenario_id)

    def list_for_run(self, run_id: str) -> list[ScenarioManifest]:
        """Return persisted manifests for one baseline run."""
        with self._lock:
            head_store = self._head_store_or_raise_locked()
            if head_store is not None:
                return sorted(
                    (
                        self._load_head_locked(head)
                        for head in head_store.list_scenario_heads(
                            baseline_run_id=run_id,
                        )
                    ),
                    key=lambda manifest: (manifest.id, manifest.revision),
                )
            return sorted(
                (
                    manifest
                    for manifest in self._by_id.values()
                    if manifest.baseline_run_id == run_id
                ),
                key=lambda manifest: (manifest.id, manifest.revision),
            )

    def next_revision(self, scenario_id: str) -> int:
        """Return the next persisted revision number for a scenario id."""
        existing = self.get(scenario_id)
        return (existing.revision + 1) if existing is not None else 1

    def save(self, manifest: ScenarioManifest) -> ScenarioManifest:
        """Persist a manifest artifact and update the read-through index."""
        current = self.get(manifest.id)
        expected_revision = current.revision if current is not None else 0
        return self.save_if_current(manifest, expected_revision=expected_revision)

    def save_if_current(
        self,
        manifest: ScenarioManifest,
        *,
        expected_revision: int,
    ) -> ScenarioManifest:
        """Atomically persist only when the authorized revision is still current."""
        with self._lock:
            head_store = self._head_store_or_raise_locked()
            current = self.get(manifest.id)
            current_revision = current.revision if current is not None else 0
            if current_revision != expected_revision:
                raise conflict(
                    "Scenario changed after authorization binding",
                    code="scenario_authorization_binding_changed",
                )
            if manifest.revision != expected_revision + 1:
                raise conflict(
                    "Scenario revision does not follow the authorized revision",
                    code="scenario_revision_mismatch",
                )
            if head_store is not None:
                artifact_ref = self._persist_candidate_locked(manifest)
                committed = head_store.compare_and_set_scenario_head(
                    scenario_id=manifest.id,
                    baseline_run_id=manifest.baseline_run_id,
                    expected_revision=expected_revision,
                    new_revision=manifest.revision,
                    artifact_ref=artifact_ref,
                    manifest_hash=manifest.manifest_hash,
                )
                if not committed:
                    raise conflict(
                        "Scenario changed after authorization binding",
                        code="scenario_authorization_binding_changed",
                    )
                self._by_id[manifest.id] = manifest
                self._artifact_by_id[manifest.id] = artifact_ref
                return manifest
            return self._save_locked(manifest)

    def _persist_candidate_locked(self, manifest: ScenarioManifest) -> str:
        if self._store is None:
            raise service_unavailable(
                "Scenario artifact storage is unavailable",
                code="scenario_artifact_store_unavailable",
            )
        ref = self._store.put_json(
            manifest.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind=_SCENARIO_ARTIFACT_KIND,
                media_type="application/json",
                schema=_SCENARIO_SCHEMA,
            ),
            canon_spec=_SCENARIO_CANON,
        )
        return str(ref.artifact_id)

    def _save_locked(self, manifest: ScenarioManifest) -> ScenarioManifest:
        if self._store is None:
            self._by_id[manifest.id] = manifest
            return manifest
        artifact_ref = self._persist_candidate_locked(manifest)
        self._by_id[manifest.id] = manifest
        self._artifact_by_id[manifest.id] = artifact_ref
        return manifest

    def _head_store_or_raise_locked(self) -> ScenarioHeadStore | None:
        if self._head_store is not None:
            return self._head_store
        if self._require_durable_heads:
            raise service_unavailable(
                "Durable scenario-head authority is unavailable",
                code="scenario_head_store_unavailable",
            )
        return None

    def _hydrate_heads_locked(self) -> None:
        head_store = self._head_store_or_raise_locked()
        if head_store is None:
            return
        for head in head_store.list_scenario_heads():
            self._load_head_locked(head)

    def _load_head_locked(self, head: ScenarioHeadRecord) -> ScenarioManifest:
        cached = self._by_id.get(head.scenario_id)
        if (
            cached is not None
            and self._artifact_by_id.get(head.scenario_id) == head.artifact_ref
            and cached.baseline_run_id == head.baseline_run_id
            and cached.revision == head.revision
            and cached.manifest_hash == head.manifest_hash
        ):
            return cached
        if self._store is None:
            raise service_unavailable(
                "Scenario artifact storage is unavailable",
                code="scenario_artifact_store_unavailable",
            )
        try:
            artifact_id = artifacts.ArtifactID.model_validate(head.artifact_ref)
            sidecar = self._store.get_manifest(artifact_id)
            payload = from_canonical_bytes(self._store.get_bytes(artifact_id))
            scenario = ScenarioManifest.model_validate(payload)
        except Exception as exc:
            raise service_unavailable(
                "The authoritative scenario head cannot be resolved",
                code="scenario_head_artifact_unavailable",
            ) from exc
        artifact_schema = sidecar.artifact_schema
        if (
            sidecar.kind != _SCENARIO_ARTIFACT_KIND
            or artifact_schema is None
            or artifact_schema.name != _SCENARIO_SCHEMA.name
            or artifact_schema.version != _SCENARIO_SCHEMA.version
        ):
            raise service_unavailable(
                "The authoritative scenario head has an invalid artifact contract",
                code="scenario_head_artifact_contract_invalid",
            )
        if (
            scenario.id != head.scenario_id
            or scenario.baseline_run_id != head.baseline_run_id
            or scenario.revision != head.revision
            or not scenario.manifest_hash
            or scenario.manifest_hash != head.manifest_hash
            or _manifest_hash(scenario) != head.manifest_hash
        ):
            raise service_unavailable(
                "The authoritative scenario head failed content binding",
                code="scenario_head_content_mismatch",
            )
        self._by_id[scenario.id] = scenario
        self._artifact_by_id[scenario.id] = head.artifact_ref
        return scenario

    def _hydrate_legacy(self) -> None:
        if self._store is None:
            return
        try:
            artifact_ids = self._store.iter_artifact_ids()
        except Exception:
            return
        for artifact_id in artifact_ids:
            try:
                manifest_sidecar = self._store.get_manifest(artifact_id)
                if manifest_sidecar.kind != _SCENARIO_ARTIFACT_KIND:
                    continue
                payload = from_canonical_bytes(self._store.get_bytes(artifact_id))
                scenario = ScenarioManifest.model_validate(payload)
            except (ValidationError, ValueError, TypeError, OSError):
                continue
            current = self._by_id.get(scenario.id)
            if current is None or scenario.revision >= current.revision:
                self._by_id[scenario.id] = scenario
                self._artifact_by_id[scenario.id] = str(artifact_id)


class ScenarioService:
    """Build auditable counterfactual manifests from runtime quantities."""

    def __init__(
        self,
        *,
        lineage_service: LineageService,
        temporal_service: TemporalService,
        store: ArtifactStore | None = None,
        require_durable_heads: bool = False,
    ) -> None:
        self._lineage = lineage_service
        self._temporal = temporal_service
        self._store = store
        self._repository = ScenarioRepository(
            store,
            require_durable_heads=require_durable_heads,
        )
        self._manifests: dict[str, ScenarioManifest] = {}

    def bind_scenario_head_store(self, head_store: ScenarioHeadStore) -> None:
        """Bind the transactional logical-head authority used by scenario mutations."""
        self._repository.bind_head_store(head_store)

    def list_for_run(
        self,
        *,
        run: IndexedRunRecord,
        temporal_scope: TemporalScope | None,
        regime_shift_forecast_bundle_ref: str | None = None,
    ) -> list[ScenarioManifest]:
        """Return available scenario manifests for one baseline run."""
        quantities = self._decision_quantities(run, temporal_scope)
        if not quantities:
            return []
        all_persisted = self._repository.list_for_run(run.run_id)
        default_id = _default_scenario_id(run)
        manifest = next(
            (item for item in all_persisted if item.id == default_id),
            None,
        ) or self._default_manifest(
            run=run,
            quantities=quantities,
            temporal_scope=temporal_scope,
            regime_shift_forecast_bundle_ref=regime_shift_forecast_bundle_ref,
        )
        self._manifests[manifest.id] = manifest
        persisted = [
            persisted_manifest
            for persisted_manifest in all_persisted
            if persisted_manifest.id != manifest.id
        ]
        for persisted_manifest in persisted:
            self._manifests[persisted_manifest.id] = persisted_manifest
        excluded_ids = {manifest.id, *(item.id for item in persisted)}
        cached = [
            cached_manifest
            for cached_manifest in self._manifests.values()
            if cached_manifest.baseline_run_id == run.run_id
            and cached_manifest.id not in excluded_ids
        ]
        return [
            manifest,
            *sorted(persisted, key=lambda item: (item.id, item.revision)),
            *sorted(cached, key=lambda item: item.id),
        ]

    def get_manifest(self, scenario_id: str) -> ScenarioManifest:
        """Return a cached generated or saved scenario manifest."""
        manifest = self._repository.get(scenario_id) or self._manifests.get(scenario_id)
        if manifest is None:
            raise not_found(
                f"Scenario {scenario_id} is not available",
                code="scenario_not_found",
            )
        self._manifests[scenario_id] = manifest
        return manifest

    def get_persisted_manifest_or_none(self, scenario_id: str) -> ScenarioManifest | None:
        """Return only a durable scenario used for authorization collision checks."""
        return self._repository.get(scenario_id)

    def get_persisted_head_or_none(
        self,
        scenario_id: str,
    ) -> ScenarioHeadRecord | None:
        """Return the global logical head used for pre-policy collision checks."""
        return self._repository.get_head(scenario_id)

    def get_persisted_manifest_for_head(
        self,
        head: ScenarioHeadRecord,
    ) -> ScenarioManifest:
        """Resolve one exact head snapshot for authorization binding."""
        return self._repository.get_for_bound_head(head)

    def is_scenario_lineage(self, lineage_id: str) -> bool:
        """Return true when a lineage id belongs to a scenario manifest."""
        return _parse_scenario_lineage_id(lineage_id) is not None

    def build_lineage(self, lineage_id: str) -> LineageGraphView:
        """Build a full graph for scenario model, assumption, intervention or metric lineage."""
        parsed = _parse_scenario_lineage_id(lineage_id)
        if parsed is None:
            return _unresolved_scenario_lineage(lineage_id)
        scenario_id, _lineage_kind = parsed
        try:
            manifest = self.get_manifest(scenario_id)
        except Exception:
            return _unresolved_scenario_lineage(lineage_id)
        return self.build_lineage_for_manifest(lineage_id, manifest)

    def build_lineage_for_manifest(
        self,
        lineage_id: str,
        manifest: ScenarioManifest,
    ) -> LineageGraphView:
        """Build scenario lineage from one already-authorized immutable manifest."""
        parsed = _parse_scenario_lineage_id(lineage_id)
        if parsed is None or parsed[0] != manifest.id:
            raise ValueError("lineage_id must identify the supplied scenario manifest")
        _scenario_id, lineage_kind = parsed
        nodes = _scenario_lineage_nodes(
            manifest=manifest,
            lineage_id=lineage_id,
            lineage_kind=lineage_kind,
        )
        edges = _scenario_lineage_edges(
            manifest=manifest,
            lineage_id=lineage_id,
        )
        payload_for_hash = {
            "lineage_id": lineage_id,
            "manifest_hash": manifest.manifest_hash or _manifest_hash(manifest),
            "nodes": [node.model_dump(mode="json") for node in nodes],
            "edges": [edge.model_dump(mode="json") for edge in edges],
        }
        return LineageGraphView(
            id=lineage_id,
            status=_lineage_status_for_manifest(manifest),
            hash=content_hash(json.dumps(payload_for_hash, sort_keys=True), prefix=True),
            freshness="stale" if manifest.status == "stale" else "current",
            compact_summary=[
                LineageCompactSummaryItem(
                    kind="source",
                    label=manifest.baseline_run_id,
                    id=f"run:{manifest.baseline_run_id}:baseline",
                ),
                LineageCompactSummaryItem(
                    kind="method",
                    label=manifest.model_family,
                    id=manifest.model_lineage.id,
                ),
                LineageCompactSummaryItem(
                    kind="model",
                    label=f"{len(manifest.assumptions)} assumptions",
                    id=f"scenario:{manifest.id}:assumptions",
                ),
                LineageCompactSummaryItem(
                    kind="result",
                    label=lineage_kind,
                    id=lineage_id,
                ),
            ],
            nodes=nodes,
            edges=edges,
            exports=_scenario_export_links(lineage_id),
            metadata={
                "scenario_id": manifest.id,
                "scenario_status": manifest.status,
                "lineage_kind": lineage_kind,
                "manifest_hash": manifest.manifest_hash or _manifest_hash(manifest),
                "baseline_run_id": manifest.baseline_run_id,
            },
        )

    def export_lineage(self, lineage_id: str, *, format_name: str) -> dict[str, Any]:
        """Return deterministic OpenLineage/PROV exports for scenario lineage."""
        graph = self.build_lineage(lineage_id)
        if format_name == "openlineage":
            return {
                "eventType": "COMPLETE",
                "producer": "polisyos-runtime-api",
                "run": {"runId": graph.id},
                "job": {"namespace": "polisyos.runtime.scenario", "name": graph.id},
                "inputs": [
                    {
                        "namespace": "polisyos.scenario",
                        "name": node.id,
                        "facets": {"kind": {"kind": node.kind}},
                    }
                    for node in graph.nodes
                    if node.id != graph.id
                ],
                "outputs": [{"namespace": "polisyos.scenario", "name": graph.id}],
                "facets": {
                    "polisyos_scenario": {
                        "_producer": "polisyos-runtime-api",
                        "_schemaURL": "https://polisyos.dev/schemas/scenario-lineage",
                        **graph.metadata,
                    }
                },
            }
        if format_name == "prov":
            return {
                "prefix": {"polisyos": "https://polisyos.dev/prov/"},
                "entity": {
                    node.id: {
                        "prov:label": node.label,
                        "polisyos:kind": node.kind,
                        **node.metadata,
                    }
                    for node in graph.nodes
                },
                "wasDerivedFrom": [
                    {
                        "generatedEntity": edge.target_id,
                        "usedEntity": edge.source_id,
                        "polisyos:relation": edge.relation,
                        **edge.metadata,
                    }
                    for edge in graph.edges
                ],
            }
        raise ValueError(f"Unsupported lineage export format: {format_name}")

    def create_for_run(
        self,
        *,
        run: IndexedRunRecord,
        request: ScenarioCreateRequest,
        temporal_scope: TemporalScope | None,
        regime_shift_forecast_bundle_ref: str | None = None,
        authorized_scenario_id: str | None = None,
        expected_revision: int | None = None,
    ) -> ScenarioManifest:
        """Persist an operator-authored scenario draft in the runtime service."""
        scenario_id = authorized_scenario_id or resolve_scenario_target_id(run, request.id)
        if _normalize_scenario_id(scenario_id) != scenario_id:
            raise conflict(
                "Authorized scenario target is not canonical",
                code="scenario_authorization_binding_invalid",
            )
        if request.id is not None and resolve_scenario_target_id(run, request.id) != scenario_id:
            raise conflict(
                "Scenario target differs from the authorized target",
                code="scenario_authorization_binding_changed",
            )
        current = self._repository.get(scenario_id)
        current_revision = current.revision if current is not None else 0
        if expected_revision is not None and current_revision != expected_revision:
            raise conflict(
                "Scenario changed after authorization binding",
                code="scenario_authorization_binding_changed",
            )
        now = datetime.now(UTC).replace(microsecond=0)
        gate_verdict = _enforce_phase4_scenario_gate(
            run,
            scenario_id=scenario_id,
            store=self._store,
            regime_shift_forecast_bundle_ref=(
                regime_shift_forecast_bundle_ref or request.regime_shift_forecast_bundle_ref
            ),
        )
        manifest = ScenarioManifest(
            id=scenario_id,
            baseline_run_id=run.run_id,
            status="draft",
            lifecycle_status="saved",
            revision=current_revision + 1,
            temporal_scope=temporal_scope,
            policy_question=request.policy_question,
            author=request.author,
            affected_population=request.affected_population or run.details.cell_id,
            temporal_window=_temporal_window(run),
            model_family=request.model_family,
            model_version=request.model_version,
            model_lineage=_scenario_lineage(
                scenario_id=scenario_id,
                kind="model",
                label=request.model_family,
                status="pending",
            ),
            baseline_lineage=_baseline_lineage(run),
            baseline_hash=_baseline_hash(run),
            computed_at=now,
            validity_window=_temporal_window(run),
            known_limitations=request.known_limitations,
            interventions=request.interventions,
            assumptions=request.assumptions,
            constraints=request.constraints,
            phase4_gate_verdict=gate_verdict.model_dump(mode="json"),
        )
        manifest = _finalize_manifest_hash(
            manifest.model_copy(update={"saved_at": now}),
        )
        self._repository.save_if_current(
            manifest,
            expected_revision=current_revision,
        )
        self._manifests[scenario_id] = manifest
        return manifest

    def capabilities_for_run(
        self,
        *,
        run: IndexedRunRecord,
        temporal_scope: TemporalScope | None,
        regime_shift_forecast_bundle_ref: str | None = None,
    ) -> list[ScenarioCapability]:
        """Describe supported and unsupported counterfactual surfaces for one run."""
        quantities = self._decision_quantities(run, temporal_scope)
        if not quantities:
            return [
                ScenarioCapability(
                    surface="run_metrics",
                    supported=False,
                    reason_code="no_decision_quantities",
                    supported_modes=[],
                    limitations=["No decision-bearing QuantityValue envelopes were found."],
                ),
                ScenarioCapability(
                    surface="whatif",
                    supported=False,
                    reason_code="no_decision_quantities",
                    supported_modes=[],
                    limitations=["Scenario workbench needs at least one baseline metric."],
                ),
            ]

        capabilities = [
            ScenarioCapability(
                surface="run_metrics",
                supported=True,
                supported_modes=["actual", "actual_vs_scenario", "scenario_only"],
            ),
            ScenarioCapability(
                surface="quantities",
                supported=True,
                supported_modes=["actual", "actual_vs_scenario", "scenario_only"],
            ),
            ScenarioCapability(
                surface="lineage",
                supported=True,
                supported_modes=["actual_vs_scenario", "scenario_only"],
                limitations=["Scenario lineage is model-derived until promoted for review."],
            ),
            ScenarioCapability(
                surface="charts",
                supported=True,
                supported_modes=["actual", "actual_vs_scenario", "scenario_only"],
            ),
            ScenarioCapability(
                surface="whatif",
                supported=True,
                supported_modes=["actual_vs_scenario"],
            ),
        ]
        for quantity in quantities:
            metric_id = quantity.metric_id or quantity.label or "unknown_metric"
            supported = quantity.point is not None and quantity.lineage.status != "untraced"
            capabilities.append(
                ScenarioCapability(
                    surface="run_metrics",
                    metric_id=metric_id,
                    supported=supported,
                    reason_code=None if supported else "metric_untraced_or_non_numeric",
                    supported_modes=(
                        ["actual", "actual_vs_scenario", "scenario_only"] if supported else []
                    ),
                    limitations=[] if supported else ["Metric needs traced numeric lineage."],
                )
            )
        return capabilities

    def build_metrics(
        self,
        *,
        run: IndexedRunRecord,
        scenario_id: str,
        temporal_scope: TemporalScope | None,
        regime_shift_forecast_bundle_ref: str | None = None,
    ) -> tuple[ScenarioManifest, dict[str, CounterfactualMetric]]:
        """Return actual, scenario and delta quantities in one normalized payload."""
        quantities = self._decision_quantities(run, temporal_scope)
        if not quantities:
            raise conflict(
                "Run has no decision-bearing quantities for counterfactual metrics",
                code="scenario_metrics_unsupported",
            )
        manifest = self._repository.get(scenario_id) or self._manifests.get(scenario_id)
        if manifest is None:
            manifest = self._default_manifest(
                run=run,
                quantities=quantities,
                temporal_scope=temporal_scope,
                scenario_id=scenario_id,
                regime_shift_forecast_bundle_ref=regime_shift_forecast_bundle_ref,
            )
            self._manifests[scenario_id] = manifest
        if manifest.baseline_run_id != run.run_id:
            raise conflict(
                "Scenario baseline does not match requested run",
                code="scenario_baseline_mismatch",
            )

        scenario_ref = _scenario_ref(manifest)
        metrics: dict[str, CounterfactualMetric] = {}
        for actual in quantities:
            if actual.point is None or actual.lineage.status == "untraced":
                continue
            metric_id = actual.metric_id or actual.label or "unknown_metric"
            counterfactual = _counterfactual_quantity(
                actual,
                scenario_id=manifest.id,
                temporal_scope=temporal_scope,
                assumption_ids=[assumption.id for assumption in manifest.assumptions],
            )
            delta = _delta_quantity(
                actual=actual,
                counterfactual=counterfactual,
                scenario_id=manifest.id,
                temporal_scope=temporal_scope,
            )
            metrics[metric_id] = CounterfactualMetric(
                metric_id=metric_id,
                label=actual.label or metric_id,
                actual=actual,
                counterfactual=counterfactual,
                delta=delta,
                scenario_ref=scenario_ref,
                assumption_ids=[assumption.id for assumption in manifest.assumptions],
            )
        return manifest, metrics

    def _decision_quantities(
        self,
        run: IndexedRunRecord,
        temporal_scope: TemporalScope | None,
    ) -> list[QuantityValue]:
        quantities, _coverage, entries = self._lineage.build_quantity_inventory_for_run(run)
        quantities, _coverage, _entries = self._temporal.project_quantities(
            quantities,
            entries,
            temporal_scope,
        )
        return [quantity for quantity in quantities if quantity.quantity_class == "decision"]

    def _default_manifest(
        self,
        *,
        run: IndexedRunRecord,
        quantities: list[QuantityValue],
        temporal_scope: TemporalScope | None,
        scenario_id: str | None = None,
        regime_shift_forecast_bundle_ref: str | None = None,
    ) -> ScenarioManifest:
        resolved_id = _normalize_scenario_id(scenario_id or _default_scenario_id(run))
        gate_verdict = _enforce_phase4_scenario_gate(
            run,
            scenario_id=resolved_id,
            store=self._store,
            regime_shift_forecast_bundle_ref=regime_shift_forecast_bundle_ref,
        )
        baseline = _pick_intervention_quantity(quantities)
        assumption = ScenarioAssumption(
            id="asm_no_external_shock",
            label="No external demand shock",
            status="operator_assumption",
            lineage=_scenario_lineage(
                scenario_id=resolved_id,
                kind="assumption",
                label="No external demand shock",
                status="pending",
            ),
            description=(
                "Scenario assumes exogenous demand, model family and population remain fixed."
            ),
        )
        intervention = ScenarioIntervention(
            field=baseline.metric_id or baseline.label or "policy_input",
            operator="multiply",
            value=_intervention_value(
                baseline,
                scenario_id=resolved_id,
                temporal_scope=temporal_scope,
            ),
            baseline_value=baseline,
            constraint_ids=["baseline_scale_bounds"],
        )
        stale_reasons = _stale_reasons(quantities)
        return ScenarioManifest(
            id=resolved_id,
            baseline_run_id=run.run_id,
            status="stale" if stale_reasons else "computed",
            lifecycle_status="generated",
            temporal_scope=temporal_scope,
            policy_question="What if the primary policy lever moved within safe bounds?",
            author="PolicyOS scenario generator",
            affected_population=run.details.cell_id or run.details.tenant_id,
            temporal_window=_temporal_window(run),
            model_family="runtime-counterfactual-linearized",
            model_version="2.4",
            model_lineage=_scenario_lineage(
                scenario_id=resolved_id,
                kind="model",
                label="Runtime counterfactual linearization",
                status="pending",
            ),
            baseline_lineage=_baseline_lineage(run),
            baseline_hash=_baseline_hash(run),
            computed_at=datetime.now(UTC).replace(microsecond=0),
            validity_window=_temporal_window(run),
            known_limitations=[
                "Foundation scenario uses a bounded deterministic sensitivity transform.",
                "Promotion to verified scenario requires model execution and review.",
            ],
            stale_reasons=stale_reasons,
            interventions=[intervention],
            assumptions=[assumption],
            constraints=[
                _scale_constraint(
                    scenario_id=resolved_id,
                    baseline=baseline,
                    temporal_scope=temporal_scope,
                )
            ],
            phase4_gate_verdict=gate_verdict.model_dump(mode="json"),
        )


def _default_scenario_id(run: IndexedRunRecord) -> str:
    return _normalize_scenario_id(f"scn_{run.run_id}_bounded_shift")


def _draft_scenario_id(run: IndexedRunRecord) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return _normalize_scenario_id(f"scn_{run.run_id}_draft_{stamp}")


def resolve_scenario_target_id(
    run: IndexedRunRecord,
    requested_id: str | None,
) -> str:
    """Resolve the exact canonical scenario slot that a create request mutates."""
    return (
        _normalize_scenario_id(requested_id)
        if requested_id is not None
        else _draft_scenario_id(run)
    )


def _normalize_scenario_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_:-]+", "_", value.strip())[:160] or "scn_unnamed"


def _parse_scenario_lineage_id(lineage_id: str) -> tuple[str, str] | None:
    if not lineage_id.startswith("scenario:"):
        return None
    remainder = lineage_id.removeprefix("scenario:")
    if ":" not in remainder:
        return None
    scenario_id, lineage_kind = remainder.rsplit(":", 1)
    if not scenario_id or not lineage_kind:
        return None
    return scenario_id, lineage_kind


def _scenario_lineage_nodes(
    *,
    manifest: ScenarioManifest,
    lineage_id: str,
    lineage_kind: str,
) -> list[LineageGraphNode]:
    timestamp = manifest.computed_at
    nodes = [
        LineageGraphNode(
            id=f"run:{manifest.baseline_run_id}:baseline",
            kind="baseline_run",
            label=f"Baseline run {manifest.baseline_run_id}",
            timestamp=timestamp,
            metadata={
                "baseline_hash": manifest.baseline_hash,
                "affected_population": manifest.affected_population,
            },
        ),
        LineageGraphNode(
            id=manifest.model_lineage.id,
            kind="model",
            label=manifest.model_family,
            timestamp=timestamp,
            metadata={
                "model_version": manifest.model_version,
                "verification_status": manifest.model_lineage.status,
                "freshness": manifest.model_lineage.freshness,
            },
        ),
        LineageGraphNode(
            id=lineage_id,
            kind=f"counterfactual_{lineage_kind}",
            label=f"{manifest.policy_question} / {lineage_kind}",
            timestamp=timestamp,
            metadata={
                "scenario_id": manifest.id,
                "scenario_status": manifest.status,
                "validity_window": (
                    manifest.validity_window.model_dump(mode="json")
                    if manifest.validity_window
                    else None
                ),
                "known_limitations": list(manifest.known_limitations),
            },
        ),
    ]
    for assumption in manifest.assumptions:
        nodes.append(
            LineageGraphNode(
                id=assumption.lineage.id,
                kind="assumption",
                label=assumption.label,
                timestamp=timestamp,
                metadata={
                    "assumption_id": assumption.id,
                    "assumption_status": assumption.status,
                    "description": assumption.description,
                    "verification_status": assumption.lineage.status,
                    "freshness": assumption.lineage.freshness,
                },
            )
        )
    for intervention in manifest.interventions:
        nodes.append(
            LineageGraphNode(
                id=f"scenario:{manifest.id}:intervention:{intervention.field}",
                kind="intervention",
                label=f"{intervention.field} {intervention.operator}",
                timestamp=timestamp,
                metadata={
                    "field": intervention.field,
                    "operator": intervention.operator,
                    "constraint_ids": list(intervention.constraint_ids),
                    "value_metric_id": intervention.value.metric_id,
                    "value_point": intervention.value.point,
                    "baseline_point": (
                        intervention.baseline_value.point
                        if intervention.baseline_value is not None
                        else None
                    ),
                    "scenario_id": manifest.id,
                },
            )
        )
    for constraint in manifest.constraints:
        nodes.append(
            LineageGraphNode(
                id=f"scenario:{manifest.id}:constraint:{constraint.id}",
                kind="constraint",
                label=constraint.label,
                timestamp=timestamp,
                metadata={
                    "constraint_id": constraint.id,
                    "field": constraint.field,
                    "severity": constraint.severity,
                    "operator": constraint.operator,
                    "message": constraint.message,
                },
            )
        )
    return nodes


def _scenario_lineage_edges(
    *,
    manifest: ScenarioManifest,
    lineage_id: str,
) -> list[LineageGraphEdge]:
    edges = [
        LineageGraphEdge(
            source_id=f"run:{manifest.baseline_run_id}:baseline",
            target_id=lineage_id,
            relation="baseline_for",
        ),
        LineageGraphEdge(
            source_id=manifest.model_lineage.id,
            target_id=lineage_id,
            relation="modeled_by",
        ),
    ]
    for assumption in manifest.assumptions:
        edges.append(
            LineageGraphEdge(
                source_id=assumption.lineage.id,
                target_id=lineage_id,
                relation="assumes",
                metadata={"assumption_status": assumption.status},
            )
        )
    for intervention in manifest.interventions:
        intervention_id = f"scenario:{manifest.id}:intervention:{intervention.field}"
        edges.append(
            LineageGraphEdge(
                source_id=intervention_id,
                target_id=lineage_id,
                relation="intervenes",
            )
        )
        for constraint_id in intervention.constraint_ids:
            edges.append(
                LineageGraphEdge(
                    source_id=f"scenario:{manifest.id}:constraint:{constraint_id}",
                    target_id=intervention_id,
                    relation="constrains",
                )
            )
    return edges


def _lineage_status_for_manifest(manifest: ScenarioManifest) -> str:
    if manifest.status == "failed":
        return "disputed"
    if manifest.status in {"draft", "computed", "stale"}:
        return "pending"
    return "pending"


def _unresolved_scenario_lineage(lineage_id: str) -> LineageGraphView:
    return LineageGraphView(
        id=lineage_id,
        status="untraced",
        freshness="unknown",
        compact_summary=[
            LineageCompactSummaryItem(kind="unknown", label="Unresolved scenario lineage")
        ],
        nodes=[
            LineageGraphNode(
                id=lineage_id,
                kind="untraced",
                label="Unresolved scenario lineage",
                metadata={
                    "reason_code": "scenario_lineage_not_resolved",
                    "tracking_issue": "policyos://counterfactual/scenario-lineage",
                },
            )
        ],
        edges=[],
        exports=_scenario_export_links(lineage_id),
        metadata={
            "reason_code": "scenario_lineage_not_resolved",
            "tracking_issue": "policyos://counterfactual/scenario-lineage",
        },
    )


def _scenario_export_links(lineage_id: str) -> LineageExportLinks:
    return LineageExportLinks(
        openlineage=f"/api/v1/lineage/{lineage_id}/export/openlineage",
        prov=f"/api/v1/lineage/{lineage_id}/export/prov",
    )


def _pick_intervention_quantity(quantities: list[QuantityValue]) -> QuantityValue:
    ranked = sorted(
        quantities,
        key=lambda quantity: (
            0 if _prefers_as_policy_lever(quantity) else 1,
            quantity.metric_id or quantity.label or "",
        ),
    )
    return ranked[0]


def _prefers_as_policy_lever(quantity: QuantityValue) -> bool:
    metric_id = (quantity.metric_id or "").lower()
    return any(token in metric_id for token in ("cost", "budget"))


def _intervention_value(
    baseline: QuantityValue,
    *,
    scenario_id: str,
    temporal_scope: TemporalScope | None,
) -> QuantityValue:
    multiplier = _metric_multiplier(baseline)
    point = _scale_point(baseline.point, multiplier)
    return QuantityValue(
        point=point,
        unit=baseline.unit,
        metric_id=f"{baseline.metric_id or 'metric'}.intervention",
        label=f"{baseline.label or baseline.metric_id or 'Metric'} intervention",
        lineage=_scenario_lineage(
            scenario_id=scenario_id,
            kind="intervention",
            label="Operator intervention",
            status="pending",
        ),
        uncertainty=baseline.uncertainty,
        time=_temporal_ref(baseline, temporal_scope, scenario_id=scenario_id),
        quantity_class="decision",
    )


def _counterfactual_quantity(
    actual: QuantityValue,
    *,
    scenario_id: str,
    temporal_scope: TemporalScope | None,
    assumption_ids: list[str],
) -> QuantityValue:
    multiplier = _metric_multiplier(actual)
    point = _scale_point(actual.point, multiplier)
    return QuantityValue(
        point=point,
        unit=actual.unit,
        metric_id=f"{actual.metric_id or 'metric'}.counterfactual",
        label=f"{actual.label or actual.metric_id or 'Metric'} scenario value",
        lineage=_scenario_lineage(
            scenario_id=scenario_id,
            kind="projection",
            label=actual.label or actual.metric_id or "Scenario metric",
            status="pending",
            assumption_ids=assumption_ids,
        ),
        uncertainty=_scale_uncertainty(actual.uncertainty, multiplier),
        time=_temporal_ref(actual, temporal_scope, scenario_id=scenario_id),
        quantity_class="decision",
    )


def _delta_quantity(
    *,
    actual: QuantityValue,
    counterfactual: QuantityValue,
    scenario_id: str,
    temporal_scope: TemporalScope | None,
) -> QuantityValue:
    point = None
    if actual.point is not None and counterfactual.point is not None:
        point = counterfactual.point - actual.point
    metric_id = actual.metric_id or "metric"
    return QuantityValue(
        point=point,
        unit=actual.unit,
        metric_id=f"{metric_id}.counterfactual_delta",
        label=f"{actual.label or metric_id} scenario delta",
        lineage=_scenario_lineage(
            scenario_id=scenario_id,
            kind="delta",
            label="Counterfactual delta",
            status="pending",
        ),
        uncertainty=_delta_uncertainty(actual, counterfactual),
        time=_temporal_ref(actual, temporal_scope, scenario_id=scenario_id),
        quantity_class="decision",
    )


def _metric_multiplier(quantity: QuantityValue) -> float:
    metric_id = (quantity.metric_id or quantity.label or "").lower()
    if any(token in metric_id for token in ("cost", "budget", "risk", "latency")):
        return 0.9
    return 1.05


def _scale_point(value: float | None, multiplier: float) -> float | None:
    if value is None or not isfinite(value):
        return None
    return round(value * multiplier, 8)


def _scale_uncertainty(
    uncertainty: QuantityUncertainty | None,
    multiplier: float,
) -> QuantityUncertainty | None:
    if uncertainty is None:
        return None
    return QuantityUncertainty(
        ci_80=_scale_interval(uncertainty.ci_80, multiplier),
        ci_95=_scale_interval(uncertainty.ci_95, multiplier),
        quantiles={
            key: round(value * multiplier, 8) for key, value in uncertainty.quantiles.items()
        },
        method="simulation",
        identifiability="assumed",
        disputed=uncertainty.disputed,
    )


def _scale_interval(
    interval: tuple[float, float] | None,
    multiplier: float,
) -> tuple[float, float] | None:
    if interval is None:
        return None
    values = sorted((interval[0] * multiplier, interval[1] * multiplier))
    return (round(values[0], 8), round(values[1], 8))


def _delta_uncertainty(
    actual: QuantityValue,
    counterfactual: QuantityValue,
) -> QuantityUncertainty | None:
    actual_ci = actual.uncertainty.ci_95 if actual.uncertainty else None
    counterfactual_ci = counterfactual.uncertainty.ci_95 if counterfactual.uncertainty else None
    if actual_ci is None or counterfactual_ci is None:
        return None
    return QuantityUncertainty(
        ci_95=(counterfactual_ci[0] - actual_ci[1], counterfactual_ci[1] - actual_ci[0]),
        method="simulation",
        identifiability="assumed",
        disputed=bool(
            (actual.uncertainty.disputed if actual.uncertainty else False)
            or (counterfactual.uncertainty.disputed if counterfactual.uncertainty else False)
        ),
    )


def _temporal_ref(
    quantity: QuantityValue,
    temporal_scope: TemporalScope | None,
    *,
    scenario_id: str,
) -> TemporalRef:
    if temporal_scope is not None:
        return TemporalRef(
            valid_at=temporal_scope.valid_at,
            tx_at=temporal_scope.tx_at,
            branch=temporal_scope.branch,
            snapshot_id=temporal_scope.snapshot_id,
            scenario_id=scenario_id,
        )
    if quantity.time is not None:
        return TemporalRef(
            valid_at=quantity.time.valid_at,
            tx_at=quantity.time.tx_at,
            branch=quantity.time.branch,
            snapshot_id=quantity.time.snapshot_id,
            scenario_id=scenario_id,
        )
    return TemporalRef(
        scenario_id=scenario_id,
    )


def _scenario_ref(manifest: ScenarioManifest) -> ScenarioRef:
    return ScenarioRef(
        id=manifest.id,
        status=manifest.status,
        baseline_run_id=manifest.baseline_run_id,
        temporal_scope=manifest.temporal_scope,
        lineage=manifest.model_lineage,
        assumption_ids=[assumption.id for assumption in manifest.assumptions],
        manifest_hash=manifest.manifest_hash or _manifest_hash(manifest),
    )


def _scenario_lineage(
    *,
    scenario_id: str,
    kind: str,
    label: str,
    status: str,
    assumption_ids: list[str] | None = None,
) -> LineageRef:
    summary = {
        "source": scenario_id,
        "method": "counterfactual scenario",
        "kind": kind,
    }
    if assumption_ids:
        summary["assumptions"] = ",".join(sorted(assumption_ids))
    return LineageRef(
        id=f"scenario:{scenario_id}:{kind}",
        status=status,
        freshness="current",
        summary=summary,
        compact_summary=[
            LineageCompactSummaryItem(kind="source", label=scenario_id),
            LineageCompactSummaryItem(kind="method", label="Counterfactual scenario"),
            LineageCompactSummaryItem(kind="result", label=label),
        ],
    )


def _baseline_lineage(run: IndexedRunRecord) -> LineageRef:
    return LineageRef(
        id=f"run:{run.run_id}:baseline",
        status="verified",
        freshness="current",
        summary={"source": run.run_id, "method": "baseline run"},
        compact_summary=[
            LineageCompactSummaryItem(kind="source", label=run.run_id),
            LineageCompactSummaryItem(kind="result", label="Baseline run"),
        ],
    )


def _baseline_hash(run: IndexedRunRecord) -> str:
    return content_hash(
        f"{run.run_id}:{run.details.started_at}:{run.details.finished_at}:{run.details.status}",
        prefix=True,
    )


def _manifest_hash(manifest: ScenarioManifest) -> str:
    payload = manifest.model_dump(mode="json", exclude={"manifest_hash"})
    return content_hash(to_canonical_bytes(payload, spec=_SCENARIO_CANON), prefix=True)


def _finalize_manifest_hash(manifest: ScenarioManifest) -> ScenarioManifest:
    """Return a copy with a manifest hash derived from every field except itself."""
    return manifest.model_copy(update={"manifest_hash": _manifest_hash(manifest)})


def _temporal_window(run: IndexedRunRecord) -> TemporalRange:
    return TemporalRange(earliest=run.details.started_at, latest=run.details.finished_at)


def _enforce_phase4_scenario_gate(
    run: IndexedRunRecord,
    *,
    scenario_id: str,
    store: ArtifactStore | None = None,
    regime_shift_forecast_bundle_ref: str | None = None,
) -> Phase4TemporalPolicyGateVerdict:
    window = _temporal_window(run)
    horizon = _phase4_horizon_from_window(window)
    verdict = validate_phase4_temporal_policy_query(
        horizon=horizon,
        regime_bundle=None,
        regime_bundle_ref=regime_shift_forecast_bundle_ref,
        artifact_store=store,
        metadata={
            "surface": "runtime.scenario",
            "run_id": run.run_id,
            "scenario_id": scenario_id,
        },
    )
    if not verdict.allowed:
        raise conflict(
            "Scenario uses a long temporal horizon without calibrated regime status",
            code=Phase4DynamicsGateError.code,
            extensions={"phase4_gate_verdict": verdict.model_dump(mode="json")},
        )
    return verdict


def _phase4_horizon_from_window(window: TemporalRange) -> int:
    if window.earliest is None or window.latest is None:
        return 1
    seconds = max((window.latest - window.earliest).total_seconds(), 0.0)
    months = math.ceil(seconds / (30.0 * 24.0 * 60.0 * 60.0))
    return max(1, months)


def _scale_constraint(
    *,
    scenario_id: str,
    baseline: QuantityValue,
    temporal_scope: TemporalScope | None,
) -> ScenarioConstraint:
    return ScenarioConstraint(
        id="baseline_scale_bounds",
        label="Intervention remains within 10 percent of baseline",
        field=baseline.metric_id or baseline.label,
        severity="warning",
        operator="within_multiplier",
        value=QuantityValue(
            point=0.1,
            unit=UnitRef(code="1", system="ucum", display="ratio"),
            metric_id="scenario.scale_bound",
            label="Scenario scale bound",
            lineage=_scenario_lineage(
                scenario_id=scenario_id,
                kind="constraint",
                label="Scale bound",
                status="pending",
            ),
            time=TemporalRef(
                valid_at=temporal_scope.valid_at if temporal_scope else None,
                tx_at=temporal_scope.tx_at if temporal_scope else None,
                branch=temporal_scope.branch if temporal_scope else None,
                snapshot_id=temporal_scope.snapshot_id if temporal_scope else None,
                scenario_id=scenario_id,
            ),
            quantity_class="decision",
        ),
        message="Foundation scenario is intentionally bounded until model execution runs.",
    )


def _stale_reasons(quantities: list[QuantityValue]) -> list[str]:
    reasons: list[str] = []
    if any(quantity.lineage.freshness == "stale" for quantity in quantities):
        reasons.append("baseline_lineage_stale")
    if any(
        quantity.lineage.status in {"pending", "disputed", "untraced"} for quantity in quantities
    ):
        reasons.append("baseline_not_fully_verified")
    return reasons
