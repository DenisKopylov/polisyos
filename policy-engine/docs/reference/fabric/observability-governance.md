# Fabric Observability And Governance

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Freshness: 2026-10-14
Owner: `@fabric-owners`
Source pin: `c35222b3dcf103338175cf300c5fe9487e6416f3`
Source plan: `docs/plans/active/FABRIC_BEST_IN_CLASS_PLAN.md`, Phase 4.
Source of truth: `src/polisyos/fabric/_adapters/observability.py`, `src/polisyos/ir/connectors/`, `src/polisyos/fabric/connectors/governance_metadata.py`, `src/polisyos/fabric/security/**`, `src/polisyos/fabric/connectors/quality/evidence.py`, `src/polisyos/scientist/governance/passes/quality_gate_pass.py`
Evidence level: implementation and named unit-test behavior inspected at the source pin. Tests were not run in this documentation pass; live telemetry and operational SLO attainment are not established.
Best-in-class inventory: [best-in-class-inventory.md](best-in-class-inventory.md)

Fabric defines observability names, governance metadata, quality-evidence
builders, and an SLI/SLO evaluation surface. Runtime behavior is
backend-neutral: telemetry backends can consume the declared names. This
reference describes contracts and consumers, not measurements from a live
deployment.

## SLI And SLO Contract

| SLI | Direction | Default objective | Priority | Window |
| --- | --- | ---: | --- | --- |
| `fetch_success` | at least | `0.995` | `P0` | `rolling_7d` |
| `schema_compliance` | at least | `0.999` | `P0` | `rolling_7d` |
| `data_freshness` | at most | `86400s` | `P1` | `rolling_24h` |
| `materialization_freshness` | at most | `3600s` | `P1` | `rolling_24h` |
| `lineage_coverage` | at least | `0.99` | `P1` | `rolling_7d` |
| `replay_success` | at least | `0.99` | `P1` | `rolling_7d` |
| `quarantine_rate` | at most | `0.01` | `P1` | `rolling_24h` |
| `query_latency` | at most | `1.0s` | `P1` | `rolling_24h` |

`evaluate_fabric_reliability_budget()` converts SLI observations into a
`FabricReliabilityReport`. `assert_fabric_feature_expansion_allowed()` raises
`FabricReliabilityBudgetError` when P0/P1 budget is burned. Feature expansion
for P0/P1 Fabric work should pause until the report is healthy or an explicit
accepted-risk decision is recorded.

The table lists default objectives, not observed values. The evaluator compares
caller-supplied observations with those targets; a configured SLI, metric name,
or gate function does not establish that a backend is emitting or measuring it
in a deployed system.

`build_fabric_health_snapshot()` can include SLO observations as an optional
`slo` component. A failing SLO component emits a backend-neutral critical
`FabricAlert`.

## Telemetry Contract

| Surface | Contract |
| --- | --- |
| Trace names | `FABRIC_TRACE_NAMES`, including connector fetch, retry, circuit, cache, transform, data-plane, materialization, and query spans |
| Metric names | `FABRIC_METRIC_NAMES`, including connector latency/rows/bytes, query latency, materialization lag, quality score, freshness age, lineage graph size, DLQ count, SLI value, and error-budget burn |
| Cardinality | `FABRIC_LABEL_CARDINALITY_LIMITS` caps connector, namespace, operation, status, component, and severity labels |
| Error taxonomy | `FABRIC_ERROR_TAXONOMY` normalizes validation, timeout, rate-limit, stale-data, lineage, uncertain-state, and internal-error reasons |

## Connector Governance Metadata

Every production connector metadata record now carries:

- owner metadata (`owner`);
- schema metadata (`schema_id` or `schema_id_template`, plus `schema_registry_ref`);
- quality metadata (`quality_tier`, `quality_contract_id`, optional `quality_contract_ref`);
- SLA metadata (`availability_target`, `freshness_slo_seconds`, `p95_latency_ms`, `replay_success_target`);
- access metadata (`data_classification`, optional `column_classification`).

`validate_connector_governance_metadata()` is the executable gate for this
baseline. It is intentionally separate from the connector registry so docs,
CI, and runtime admission can reuse the same check without importing registry
state.

## Quality Evidence Propagation

`DataQualityReport.to_evidence()` includes quality indicators and contract
failure counts. `build_fabric_quality_governance_evidence()` normalizes that
report into a `fabric.quality.evidence.v1` payload with:

- score, tier, grade, freshness, component scores, and content hash;
- `QualityIndicators` converted to a stable dictionary;
- quality-contract result when present;
- `acceptable` and `needs_attention` governance booleans.

`QualityGatePass` stores the payload in
`ctx.state["fabric_quality_evidence"]` and indexes it by dataset in
`ctx.state["fabric_quality_evidence_by_dataset"]`.

## Lineage And Impact

`FabricLineageTracker` is a graph builder with source-to-query trace and impact
operations over a supplied graph. Connector ingestion records a bounded
source/transform graph when a transform pipeline applies; the inspected
materializer, claim producer, and query helper do not automatically extend
that graph. The all-node source-to-query test assembles those nodes directly
through the tracker, so it demonstrates graph operations rather than automatic
cross-producer lineage coverage. See the [lineage reference](lineage.md).

| Question | API |
| --- | --- |
| Where did this claim value come from? | `trace_claim_origin()` |
| Which source fields feed this output? | `trace_value_origin()` / `trace_column_lineage()` |
| What breaks if this source field changes? | `impact_analysis(source_schema_id, field)` |
| What can external lineage tools ingest? | `export_openlineage_json()` / `export_visualization_graph()` |

## Access, Audit, And Retention

Access governance is centered in `fabric.security`:

| Surface | Contract |
| --- | --- |
| Classification | `DataClassification`: public, internal, confidential, regulated PII, sensitive policy/legal signal |
| Access checks | `classification_allowed()` fails closed when scope or purpose is insufficient |
| Audit log | `AccessAuditEvent` and `JsonlAccessAuditLog` capture actor, tenant, query, dataset/table, columns, masking, decision, denied reason, cardinality bucket, and trace id |
| Retention | `RetentionPlanner` resolves cache, CAS, evidence-bundle, and world-projection retention/encryption plans |
| Governed writes | `resolve_artifact_governance()` enforces encryption before persistence when policy requires it |

## Runbook Coverage

| Incident class | Runbook |
| --- | --- |
| Cache storm or stale cache rebuild | [Cache Rebuild Storm](../../runbooks/cache-rebuild-storm.md) |
| Quarantine, DLQ, or data-plane recovery | [Fabric Quarantine/DLQ And Data-Plane Recovery](../../runbooks/fabric-quarantine-dlq-and-data-plane-recovery.md) |
| Replay or restore workflow | [Replay or Restore Workflow](../../runbooks/replay-or-restore.md) |
| Retained artifact recovery | [Retained Artifact Recovery](../../runbooks/retained-artifact-recovery.md) |
| Corrupted artifact or manifest | [Artifact Corruption Recovery](../../runbooks/artifact-corruption-recovery.md) |

## Validation Anchors

```bash
uv run pytest tests/unit/fabric/test_observability_governance_quality_phase4.py -q
uv run pytest tests/unit/fabric/test_fabric_observability.py tests/unit/fabric/test_lineage.py tests/unit/fabric/test_access_control.py -q
uv run pytest tests/unit/fabric/connectors/test_quality_statistics.py tests/unit/scientist/governance/test_quality_gate_pass.py -q
```

## API Reference

::: polisyos.fabric._adapters.observability

::: polisyos.fabric.connectors.governance_metadata

::: polisyos.fabric.connectors.quality.evidence
