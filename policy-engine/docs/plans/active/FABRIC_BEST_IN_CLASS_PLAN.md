---
title: Fabric Best-in-Class Plan
status: active
owner: fabric-owners
created: 2026-04-26
last_verified: 2026-04-27
stability: draft
---

# PolicyOS Fabric — Best-in-Class Plan

> Fabric is not a data-access layer. Fabric is the evidentiary memory,
> reproducibility substrate, and trust spine of PolicyOS.
>
> This plan turns `polisyos.fabric` from a strong SOTA data-fabric package into
> a best-in-class policy intelligence substrate: every decision-bearing fact is
> contract-backed, temporally reproducible, lineage-traceable, quality-scored,
> access-governed, and explainable all the way back to raw evidence.

## 0. TL;DR

`polisyos.fabric` already has serious foundations: connector contracts,
profiles, CAS evidence, document/claim pipelines, quality reports, quarantine,
semantic diff, lineage, world materialization, and bitemporal time travel.
The next step is not "more data plumbing". The next step is a stronger product
law:

**No decision-bearing data may cross from Fabric into Scientist, Scholar, Lex,
Foundry, Runtime, or the frontend without a typed envelope containing value,
source contract, temporal scope, quality, lineage, access classification,
trust status, and reproducibility metadata.**

The plan has three layers:

1. **Wave 1 — Hardening to SOTA:** close security, correctness, concurrency,
   bounded-state, schema, observability, lineage, quality, access-control, and
   time-travel gaps already identified in `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`.
2. **Wave 2 — Best-in-class primitives:** make Fabric the backend spine for
   `QuantityValue`, `TemporalScope`, provenance-on-hover, Trust View, policy
   diff, counterfactual layer, replay, and branchable world state.
3. **Wave R — Research agenda:** isolate problems that require proof,
   calibration, impossibility results, or benchmarked empirical evidence before
   the system may claim stronger guarantees.

This document is intentionally broader than remediation. The remediation plan
answers "what is unsafe or incomplete today?" This plan answers "what must be
true for Fabric to become the category-defining policy data substrate?"

## 1. Source of Truth

| Concern | Source |
| ------- | ------ |
| Existing Fabric remediation | `policy-engine/docs/FABRIC_AUDIT_REMEDIATION_PLAN.md` |
| Fabric reference surface | `policy-engine/docs/reference/fabric/**` |
| Fabric package boundary | `policy-engine/src/polisyos/fabric/README.md` |
| Fabric tests | `policy-engine/tests/fabric/**` |
| Design integration | `policy-engine/docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md` |
| Foundry research model | `policy-engine/docs/archive/plans/FOUNDRY_METHODS_RESEARCH_AGENDA.md` |
| Causal research model | `policy-engine/docs/archive/plans/CAUSAL_ENGINE_RESEARCH_AGENDA.md` |
| Public facade | `policy-engine/docs/reference/public-surface.md` |
| Repository topology | `policy-engine/docs/plans/active/REPOSITORY_SOTA_PLAN.md` |

## 2. Current State

As of this plan, Fabric already exposes:

- stable lazy facade through `polisyos.fabric`;
- connector-backed ingestion and compatibility bridge;
- 20 concrete connector classes and 38 built-in `SourceProfile` instances;
- connector contracts, schema evolution, governance snapshots, and CI checks;
- batch, record, replay, streaming-windowed, CDC, cursor, quarantine, semantic
  diff, and benchmark surfaces;
- document-to-claim and claim-to-world pipelines;
- `FabricLineageTracker`, OpenLineage export, visualization graph export, and
  impact analysis;
- `QualityIndicators`, `DataFitnessReport`, dataset validation, drift/anomaly
  checks, and quality contracts;
- append-only world fact/event store, DuckDB materialization, optional Kuzu
  graph export, retained snapshots, branches, and bitemporal world queries;
- access-control, PII, trust adapters, and tenant CAS surfaces.

The remaining gap is not architectural ambition. The gap is making these
capabilities uniform, enforced, and impossible to bypass on decision paths.

## 3. External Inspiration

This plan borrows from established data-platform standards and products, but
adapts them to PolicyOS rather than cloning them.

| Source | What matters for Fabric |
| ------ | ----------------------- |
| [W3C PROV](https://www.w3.org/TR/prov-overview/) | Provenance must support attribution, processing steps, provenance-of-provenance, reproducibility, versioning, procedures, and derivation. |
| [OpenLineage](https://openlineage.io/docs/) | Lineage should use an interoperable job/run/dataset model with extensible facets, not a bespoke closed graph only PolicyOS can understand. |
| [Apache Iceberg](https://apache.github.io/iceberg/docs/1.4.2/) | Schema evolution, hidden partitioning, time travel, version rollback, serializable isolation, and optimistic concurrency are the right mental model for durable analytical state. |
| [Iceberg schema evolution](https://apache.github.io/iceberg/docs/1.4.0/evolution/) | Schema changes must be side-effect-free and ID-based where possible; renames, drops, and reorders cannot silently corrupt semantics. |
| [Delta Lake transactions](https://delta-io.github.io/delta-rs/how-delta-lake-works/delta-lake-acid-transactions/) | Production data systems need atomic writes, conflict detection, schema enforcement, constraints, and durable transaction logs. |
| [Kafka Streams processing guarantees](https://kafka.apache.org/33/streams/core-concepts/) | Exactly-once claims are valid only when input offsets, state updates, and output writes are committed atomically; otherwise Fabric should honestly claim effectively-once or at-least-once plus dedupe. |
| [OpenTelemetry](https://opentelemetry.io/docs/) | Observability must be vendor-neutral and combine traces, metrics, and logs rather than ad hoc counters per subsystem. |
| [Google SRE SLOs](https://sre.google/sre-book/service-level-objectives/) | Fabric should measure only the few SLIs users actually care about, and use error-budget state to gate risky expansion. |
| [OWASP API injection guidance](https://owasp.org/API-Security/editions/2019/en/0xa8-injection/) | Keep data separate from commands, validate with trusted libraries, prefer parameterized APIs, and bound returned records. |
| [OpenMetadata data contracts](https://docs.open-metadata.org/latest/how-to-guides/data-contracts/spec) | Data contracts should include schema, semantics, security, quality, SLA, terms of use, status, and ownership. |
| [Great Expectations](https://legacy.017.docs.greatexpectations.io/docs/) | Quality checks should be declarative, human-readable, validated per batch, and rendered as continuously updated documentation. |
| [Soda Core](https://docs.soda.io/soda-core/overview-main.html/) | Quality checks should be embeddable in pipelines and expressible as durable check language, not scattered scripts. |
| [Dagster assets](https://docs.dagster.io/) | Best-in-class data platforms reason about persistent assets, lineage, observability, and testability as one graph. |

## 4. Product Laws

These are non-negotiable once the plan is accepted.

1. **No naked decision data.** Any value used by Scientist, Scholar, Lex,
   Foundry, Runtime, or frontend decision views must be carried in a typed
   evidence envelope, not as a primitive `float`, `int`, dataframe cell, or
   unlabelled JSON field.
2. **Time is bitemporal.** Fabric distinguishes world/policy validity time
   (`valid_at`) from system knowledge time (`tx_at`). A single `as_of` is a UI
   shorthand only, never the canonical model.
3. **Provenance is a product API.** Lineage is not debug metadata. It is a
   stable API that supports compact summaries, full graphs, raw evidence links,
   OpenLineage/PROV export, redaction, and impact analysis.
4. **Quality is decision input.** Freshness, missingness, drift, anomaly,
   schema violations, source reliability, and contract status must affect
   downstream readiness and trust, not live in a detached report.
5. **Schema changes are governed migrations.** Any change that can alter
   meaning requires compatibility classification, migration evidence, downstream
   impact, owner approval, and a replay fixture.
6. **Security is part of the data contract.** Classification, access policy,
   retention, PII tier, allowed use, and tenant scope are data-plane facts.
7. **No silent degradation.** Every failure is a typed hard failure, retryable
   transient, degraded outcome, quarantine record, accepted risk, or explicit
   unsupported capability.
8. **Replay is a first-class feature.** Fabric must be able to reproduce the
   same query/result/lineage/quality state from captured evidence and temporal
   scope without re-fetching the external world.
9. **Bounded by default.** Runtime maps, queues, caches, audit logs, resolver
   state, entity candidates, and lineage expansion all have TTL, max size, LRU,
   sampling, or persistence strategy.
10. **Claims match guarantees.** If a path is at-least-once with dedupe, it is
    labelled that way. If a claim is only narrow-accepted, its scope is visible
    in the artifact.

## 5. Non-Goals

- Do not replace Fabric with a generic lakehouse, catalog, or orchestration
  product. Fabric's job is policy evidence and world-state semantics.
- Do not duplicate Foundry method logic in Fabric. Fabric owns data truth,
  not estimator truth.
- Do not move Lex/Scholar document semantics into Fabric beyond document,
  claim, citation, and evidence pipeline primitives.
- Do not build AI discovery before source contracts, lineage, quality, access,
  and replay are enforceable.
- Do not claim exactly-once semantics where the implementation provides only
  at-least-once with idempotency/dedupe.
- Do not make OpenLineage or PROV the internal model wholesale. They are export
  and interoperability targets; PolicyOS may need richer policy-domain facets.

## 6. Architecture Target

Best-in-class Fabric has five planes.

| Plane | Purpose | Representative surfaces |
| ----- | ------- | ----------------------- |
| Source Plane | Fetch external data safely and deterministically | connectors, profiles, source trust, contracts, replay fixtures |
| Evidence Plane | Persist raw/source evidence with content addressing | CAS, evidence bundles, citations, quarantine, retention |
| Semantics Plane | Convert external records into typed policy-world facts | schema evolution, units, canonical IDs, docs/claims, entity resolution |
| World Plane | Materialize branchable, bitemporal, queryable world state | fact/event store, DuckDB/Kuzu, snapshots, branches, semantic diff |
| Trust Plane | Expose quality, lineage, access, provenance, and readiness | quality reports, lineage API, Trust View metadata, exports, impact analysis |

## 7. Canonical Envelopes

### 7.1. `FabricEvidenceEnvelope`

Every persisted source artifact should have:

- `evidence_ref`: CAS reference and content hash;
- `source_ref`: connector id, dataset id, source profile, source contract;
- `retrieval`: fetched_at, request hash, response metadata, retry/degrade state;
- `classification`: PII tier, confidentiality, retention, tenant scope;
- `contract_status`: schema, semantic, quality, SLA, terms status;
- `lineage_seed`: upstream source node and run/job identifiers;
- `replay`: record/replay fixture pointer or explicit non-replayable reason.

### 7.2. `FabricFactEnvelope`

Every world fact/event should have:

- `fact_ref` or `event_ref`;
- `value` with unit and semantic type;
- `valid_time` and `tx_time`;
- `source_evidence_refs`;
- `quality_snapshot_ref`;
- `lineage_ref`;
- `trust_status`;
- `access_policy_ref`;
- `schema_version`;
- `mutation_policy`: append-only, correction, revocation, branch-only, merge.

### 7.3. `FabricDecisionData`

Any Fabric value exported to Runtime/Scientist/UI should map cleanly into:

- `QuantityValue` for numeric decision values;
- `AuthoredText` / citation-backed text for narrative values;
- `TemporalScope` for every time-sensitive query;
- `LineageRef` with compact and full graph paths;
- `QualityRef` with machine-readable decision impact;
- `AccessRef` with redaction and allowed-use metadata;
- `ReplayRef` for deterministic reproduction.

## 8. Phased Roadmap

### Wave 1 — SOTA Hardening

Wave 1 makes the existing fabric safe enough to become the default path for
decision-bearing data.

| Phase | Theme | Exit criteria |
| ----- | ----- | ------------- |
| 0 | Baseline inventory and measurement | Current facade, contracts, docs, tests, source families, lineage coverage, quality coverage, and replay coverage are machine-inventoried. |
| 1 | Security and data-integrity containment | P0 injection, unsafe input, decompression, dynamic loading, serialization, and UTC defects are closed or accepted-risk recorded. |
| 2 | Concurrency, lifecycle, and bounded state | Pools, registries, caches, resilience maps, cursor/segment writes, queues, and resolver state have ownership and stress tests. |
| 3 | Schema, units, and semantic correctness | Schema evolution, type coercion, units, canonical IDs, non-finite values, and transform determinism are tested and governed. |
| 4 | Observability, lineage, access, and quality baseline | OTel metrics/spans/log correlation, lineage/impact APIs, schema gates, access audit, retention, quality contracts, and SLOs are live. |

#### Phase 0 — Baseline Inventory

**Deliverables**

- `tools/quality/validation/fabric_best_in_class_inventory.py`
- `tools/quality/validation/fabric_best_in_class_manifest.json`
- `tools/quality/validation/run_fabric_best_in_class_inventory.sh`
- `docs/reference/fabric/best-in-class-inventory.md`
- `tests/tools/test_fabric_best_in_class_inventory.py`
- coverage report for:
  - source contracts;
  - source profiles;
  - replay fixtures;
  - quality contracts;
  - lineage nodes/edges;
  - temporal support;
  - access classification;
  - public facade exports;
  - tests mapped to each Fabric plane.

**Acceptance**

- Inventory runs in CI report-only.
- Manifest distinguishes `implemented`, `partial`, `missing`, `not_applicable`,
  and `accepted_risk`.
- Existing Fabric reference docs point to the inventory artifact.

**Execution detail**

The inventory is the measurement spine for the rest of this plan. It must not
change runtime behavior. It only reads repository files and emits machine-
readable status.

Workstreams:

1. **F0A — Manifest schema and status model**
   - Define status enum: `implemented`, `partial`, `missing`,
     `not_applicable`, `accepted_risk`, `blocked_by_research`.
   - Define severity: `P0`, `P1`, `P2`, `P3`.
   - Define phase owner, source files, tests, docs, and evidence fields.
   - Add `accepted_risk` fields: owner, reason, review date, expiry date.

2. **F0B — Collectors**
   - Source contracts: read `schemas/snapshots/fabric/connector_contract_registry.json`
     and `schemas/snapshots/connectors/contracts.json`.
   - Connector surface: inspect `src/polisyos/fabric/connectors/sources/**`,
     entry points in `pyproject.toml`, and built-in source profiles.
   - Quality surface: inspect `src/polisyos/fabric/quality.py`,
     `src/polisyos/fabric/connectors/quality/**`, and quality tests.
   - Lineage surface: inspect `src/polisyos/fabric/provenance/lineage.py`,
     OpenLineage/PROV exports, and lineage tests.
   - Temporal surface: inspect `src/polisyos/fabric/world_query.py`,
     `src/polisyos/fabric/world/store/snapshots.py`, and time-travel tests.
   - Replay/quarantine: inspect `src/polisyos/fabric/data_plane/replay_store.py`,
     `src/polisyos/fabric/data_plane/quarantine.py`, and related tests.
   - Runtime adapters: inspect existing `src/polisyos/runtime/http/routes/{lineage,temporal}.py`
     and `src/polisyos/runtime/http/services/{lineage,temporal}.py`.

3. **F0C — Report page**
   - Render `docs/reference/fabric/best-in-class-inventory.md` from the
     manifest.
   - Show one table per plane: Source, Evidence, Semantics, World, Trust.
   - Show gaps by phase and priority.
   - Link every `missing` and `partial` item to an owner, issue, or follow-up
     placeholder.

4. **F0D — Ratchet mode**
   - First PR: report-only.
   - After Wave 1 hardening: P0/P1 `missing` entries fail CI unless they carry
     `accepted_risk`.
   - After Phase 6: decision-bearing `untraced`, `unknown_quality`, and
     `non_replayable` statuses require reason codes.

Manifest sketch:

```jsonc
{
  "schema_version": "fabric.best_in_class_manifest.v1",
  "generated_at": "2026-04-26T00:00:00Z",
  "phase": 0,
  "surfaces": [
    {
      "id": "source_contracts.worldbank.wdi",
      "plane": "source",
      "status": "implemented",
      "priority": "P1",
      "owner": "@fabric-owners",
      "source_files": [
        "src/polisyos/fabric/connectors/sources/world_bank.py"
      ],
      "tests": [
        "tests/fabric/connectors/test_contract_system.py"
      ],
      "docs": [
        "docs/reference/fabric/connectors.md"
      ],
      "evidence": {
        "contract_snapshot": "schemas/snapshots/fabric/connector_contract_registry.json"
      }
    }
  ]
}
```

Validation:

```bash
uv run python tools/quality/validation/fabric_best_in_class_inventory.py --check
uv run pytest tests/tools/test_fabric_best_in_class_inventory.py -q
```

#### Phase 1 — Security and Integrity

This phase consumes Phase 0 of `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`.

**Scope**

- query/filter injection hardening;
- safe path and URL segment handling;
- bounded response/JSON/decompression;
- safe transform loading;
- provenance/export escaping;
- UTC-aware persisted time only;
- finite numeric validation at trust boundaries.

**Acceptance**

- malicious SPARQL/SQL/SoQL/ODSQL/URL/data-path fixtures pass;
- no unreviewed raw query interpolation in Fabric;
- all persisted datetimes are timezone-aware UTC;
- NaN/Inf values are rejected, quarantined, or explicitly represented as
  typed missingness/unknown, never silently scored.

#### Phase 2 — Concurrency and Bounded Runtime

This phase consumes Phase 1 of `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`.

**Scope**

- deterministic resource lifecycle;
- atomic writes for cursor, segment, registry, schema, and report artifacts;
- contention-safe circuit breakers, rate limiters, cache metrics, and fallback;
- immutable or locked shared state;
- bounded cache, prefetch, audit, resolver, entity-candidate, and lineage state.

**Acceptance**

- stress tests cover high-contention connectors, cache, resilience, and cursor
  paths;
- crash/restart tests prove no partial cursor/segment writes become current;
- all long-lived runtime maps have a bounded-state strategy.

#### Phase 3 — Schema and Semantic Correctness

This phase consumes Phase 2 of `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`.

**Scope**

- source schema IDs and stable field IDs;
- side-effect-free schema evolution where possible;
- unit registry and affine unit handling;
- contract-aware transforms;
- semantic type validation;
- locale/decimal/Unicode normalization;
- quality finite-value boundaries;
- property tests for schema merge/evolution.

**Acceptance**

- breaking, compatible, and metadata-only changes are classified correctly;
- generated migration evidence exists for compatible changes;
- incompatible semantic changes require owner/reviewer/migration note;
- unit conversions are explicit and replayable;
- schema drift cannot silently change world facts.

#### Phase 4 — Observability, Governance, and Quality Baseline

This phase consumes Phases 3 and 4 of `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`.

**Scope**

- OpenTelemetry-first spans, metrics, and log correlation;
- Fabric SLI/SLO definitions;
- column/value lineage and impact analysis;
- access control, classification, audit log, retention;
- declarative data quality contracts;
- quality evidence propagation to Scientist governance;
- runbooks for cache, quarantine, replay, retained artifacts, and corruption.

**Acceptance**

- Fabric has SLIs for fetch success, schema compliance, data freshness,
  materialization freshness, lineage coverage, replay success, quarantine rate,
  and query latency;
- P0/P1 feature expansion pauses when Fabric burns reliability budget;
- every production connector has schema, quality, SLA, access, and owner
  metadata;
- lineage can answer origin and impact questions for representative
  decision-bearing fields.

**Implementation status — 2026-04-27**

- `src/polisyos/fabric/observability.py` defines the Phase 4 SLI/SLO contract,
  reliability-budget report, health-snapshot SLO component, and P0/P1
  expansion gate.
- `src/polisyos/ir/connectors.py` and
  `src/polisyos/fabric/connectors/governance_metadata.py` make connector
  schema, quality, SLA, access, and owner metadata executable.
- `src/polisyos/fabric/connectors/quality/evidence.py` and
  `src/polisyos/scientist/governance/passes/quality_gate_pass.py` propagate
  Fabric quality evidence into Scientist governance state.
- `docs/reference/fabric/observability-governance.md` maps SLI/SLO,
  telemetry, access/audit/retention, lineage, quality evidence, and runbooks.
- Acceptance regression: `uv run pytest tests/fabric/test_observability_governance_quality_phase4.py -q`.

### Wave 2 — Best-in-Class Primitives

Wave 2 turns Fabric from strong infrastructure into the thing competitors will
have to copy.

| Phase | Theme | Exit criteria |
| ----- | ----- | ------------- |
| 5 | Contracted source platform | New source onboarding is SDK-driven, contract-first, replayable, and governed. |
| 6 | Evidence-to-quantity spine | Fabric exports decision data through typed envelopes compatible with `QuantityValue`, `TemporalScope`, and Trust View. |
| 7 | Branchable bitemporal world | World state supports reproducible time travel, branches, corrections, merges, scenarios, and impact analysis. |
| 8 | Streaming and scale semantics | Batch, CDC, stream, replay, and distributed execution have honest processing guarantees and backpressure semantics. |
| 9 | Discovery and entity intelligence | Catalog search, NL dataset resolution, entity matching, and graph reasoning are explainable, reversible, and evaluated. |
| 10 | Product/API integration closeout | Runtime, frontend, Scientist, Scholar, Lex, and Foundry consume Fabric trust envelopes without bypasses. |

#### Phase 5 — Contracted Source Platform

**Thesis:** A best-in-class Fabric makes adding a source boring: contract,
profile, quality, replay, lineage, access, and docs are generated or checked
before the connector becomes production-visible.

**Implementation status (2026-04-27):** implemented as a fail-closed,
artifact-backed source platform. The source contract snapshot currently covers
20 production-visible connectors, with conformance v2 passing for every source
and every source carrying profile, quality, replay or non-replayable reason,
lineage, classification, retention, owner/reviewer, SLO, scorecard, and docs
evidence.

Closure artifacts:

- `src/polisyos/fabric/connectors/contracts/source_contract.py`;
- `src/polisyos/fabric/connectors/sdk/`;
- `src/polisyos/fabric/connectors/testing/conformance.py`;
- `src/polisyos/fabric/connectors/scorecard.py`;
- `schemas/fabric/source_contract.schema.json`;
- `schemas/fabric/source_scorecard.schema.json`;
- `schemas/snapshots/fabric/source_contracts_v2.json`;
- `schemas/snapshots/fabric/source_scorecards.json`;
- `tools/quality/validation/fabric_source_contracts.py`;
- `docs/reference/fabric/source-platform.md`;
- `tests/fabric/connectors/test_source_contract_v2.py`;
- `tests/tools/test_fabric_source_contracts.py`.

**Deliverables**

- `fabric.connectors.sdk` authoring helpers;
- connector conformance harness v2;
- `SourceContract` template covering schema, semantics, security, quality,
  SLA, owner, terms of use, retention, replay, and source trust;
- generated source scorecards;
- source profile compatibility matrix;
- source deprecation and sunset policy;
- dedicated reference page: `docs/reference/fabric/source-platform.md`.

**Acceptance**

- every production source has:
  - contract snapshot;
  - profile;
  - quality contract;
  - replay fixture or explicit non-replayable reason;
  - lineage seed;
  - classification and retention;
  - owner and reviewer;
  - source SLO;
  - generated docs;
- new connectors fail CI without conformance evidence;
- source scorecards show freshness, reliability, schema drift, quality, and
  replay success over time.

**Preconditions**

- Wave 1 P0/P1 hardening is closed or accepted-risk recorded.
- Phase 0 inventory is running in CI report-only.
- Existing connector contracts and schema-governance checks remain green.
- No new source family becomes production-visible without a contract snapshot.

**Execution detail**

Workstreams:

1. **F5A — `SourceContract` v2**
   - Add `schemas/fabric/source_contract.schema.json`.
   - Add or extend `src/polisyos/fabric/connectors/contracts/source_contract.py`.
   - Keep compatibility with existing `ConnectorSchemaContract` while adding
     fields for semantics, security, quality, SLA, terms, replay, and source
     trust.
   - Emit compatibility evidence into the Fabric inventory manifest.

2. **F5B — Connector SDK and scaffold**
   - Add `src/polisyos/fabric/connectors/sdk/`.
   - Provide scaffold helpers for source id, dataset id, profile id, contract
     id, replay fixture id, quality contract, and documentation stub.
   - Reuse `connectors/testing/harness.py` rather than creating a second test
     framework.

3. **F5C — Conformance harness v2**
   - Add `src/polisyos/fabric/connectors/testing/conformance.py`.
   - Validate protocol compliance, bounded reads, safe filters, profile
     resolution, schema contract, quality contract, replay fixture, lineage
     seed, access classification, and SLO metadata.
   - Add fixtures for HTTP/open-data, file, object storage, SQL, GraphQL,
     GeoJSON, and event-stream families as they become production-visible.

4. **F5D — Source scorecards**
   - Add `src/polisyos/fabric/connectors/scorecard.py`.
   - Add `schemas/fabric/source_scorecard.schema.json`.
   - Score freshness, reliability, schema drift, contract violations,
     quarantine rate, replay success, latency, and source trust.
   - Render scorecards in `docs/reference/fabric/source-platform.md`.

5. **F5E — CI gate**
   - Add `tools/quality/validation/fabric_source_contracts.py`.
   - First mode: `--report`.
   - Fail-closed mode after Phase 5 acceptance: new production connector or
     entry point fails without SourceContract v2 evidence.

SourceContract v2 minimum fields:

```yaml
id: worldbank.wdi.generic
version: 1.1.0
owner: "@fabric-owners"
source:
  connector_id: worldbank
  dataset_pattern: "WDI.*"
  profile_id: worldbank.default
schema:
  fields: []
semantics:
  domain: macroeconomic_indicators
  metric_definitions: []
  canonical_ids: []
security:
  pii_tier: none
  classification: public
  tenant_scope: shared_public
quality:
  contract_ref: worldbank.wdi.quality.v1
  required_checks: []
sla:
  refresh_frequency: monthly
  max_latency: P7D
terms:
  allowed_uses: [policy_analysis, reporting]
  disallowed_uses: []
replay:
  required: true
  fixture_ref: tests/fixtures/fabric/worldbank/wdi.replay.json
lineage:
  seed_node_kind: source_dataset
source_trust:
  tier: institutional
  calibration_status: heuristic
status: active
```

Tests:

```bash
uv run pytest tests/fabric/connectors/test_contract_system.py -q
uv run pytest tests/fabric/connectors/test_protocol_compliance.py -q
uv run pytest tests/fabric/connectors/test_source_contract_v2.py -q
uv run pytest tests/tools/test_fabric_source_contracts.py -q
```

Gate:

- Phase 5 can close with existing sources partially migrated if the manifest
  lists every gap.
- New production source families after Phase 5 must be SourceContract-v2
  compliant on first merge.

#### Phase 6 — Evidence-to-Quantity Spine

**Thesis:** Design Wave 2 depends on Fabric. `QuantityValue` and provenance UI
are only credible if Fabric can supply the truth envelope behind every number.

**Deliverables**

- `FabricDecisionData` contract;
- `QualityRef`, `AccessRef`, `ReplayRef`, and richer `LineageRef`;
- batch lineage and quality lookup adapters for Runtime;
- quantity coverage report over Fabric-facing APIs;
- mapping from Fabric facts/events/claims to `QuantityValue` and `AuthoredText`;
- `untraced`, `unknown_quality`, `restricted`, and `non_replayable` typed states.

**Acceptance**

- no decision-bearing Fabric endpoint returns a naked primitive without typed
  wrapper or explicit transitional waiver;
- compact lineage summaries have p95 <= 150 ms for 50 refs in local benchmark;
- full lineage graph loads lazily and includes raw evidence/export links;
- every trust envelope echoes the `TemporalScope` used to compute it;
- Runtime can batch-fetch lineage/quality/trust metadata without N+1 behavior.

**Preconditions**

- Phase 5 has SourceContract v2 for the source families used in decision demos.
- Existing Runtime lineage and temporal route/service files are preserved:
  `src/polisyos/runtime/http/routes/lineage.py`,
  `src/polisyos/runtime/http/services/lineage.py`,
  `src/polisyos/runtime/http/routes/temporal.py`, and
  `src/polisyos/runtime/http/services/temporal.py`.
- Design Wave 2 Phase 2.0 has agreed on `QuantityValue`, `LineageRef`,
  `TemporalRef`, `UnitRef`, and `VerificationStatus` names, or Fabric uses a
  compatibility adapter until those contracts land.

**Execution detail**

Workstreams:

1. **F6A — Fabric trust envelope**
   - Add `src/polisyos/fabric/decision_data.py`.
   - Add `schemas/fabric/trust_envelope.schema.json`.
   - Define `FabricDecisionData`, `QualityRef`, `AccessRef`, `ReplayRef`,
     `LineageRef`, `TemporalRef`, and typed gap states.
   - Keep the envelope serializable without importing frontend or Runtime code.

2. **F6B — Fabric-to-Runtime adapters**
   - Extend `src/polisyos/runtime/http/services/lineage.py` to map
     `FabricLineageTracker` and artifact lineage into compact/full runtime
     views.
   - Extend `src/polisyos/runtime/http/routes/lineage.py` with batch lookup if
     not already exposed.
   - Extend `src/polisyos/runtime/http/services/temporal.py` to echo
     `TemporalScope` on trust/lineage responses.
   - Add `GET /api/v1/runs/{run_id}/fabric-decision-data` or fold the same
     payload into existing run detail endpoints behind an additive field.

3. **F6C — Coverage scanner**
   - Add `tools/quality/validation/fabric_decision_data_coverage.py`.
   - Classify fields as `decision`, `telemetry`, `layout`, `debug`, or
     `unknown`.
   - Report naked decision values and allowed transitional waivers.

4. **F6D — Typed gap states**
   - `untraced`: requires reason code and owner.
   - `unknown_quality`: requires quality surface and remediation link.
   - `restricted`: requires access policy and redaction behavior.
   - `non_replayable`: requires source reason and retention alternative.
   - `unsupported_temporal_scope`: requires capability endpoint visibility.

5. **F6E — Performance and UX constraints**
   - Compact batch lookup: p95 <= 150 ms for 50 refs in local benchmark.
   - Full graph lookup: lazy, p95 <= 500 ms for representative run lineage.
   - No N+1 fetch pattern in run detail, provenance hover, or Trust View.

Payload sketch:

```jsonc
{
  "id": "fabric_decision_data:run_123:effect_size",
  "kind": "quantity",
  "value": {
    "point": 0.23,
    "unit": {"code": "1", "system": "ucum", "display": "ratio"},
    "semantic_type": "effect_size"
  },
  "source_contract": {
    "id": "worldbank.wdi.generic",
    "version": "1.1.0"
  },
  "quality": {
    "status": "passed",
    "score": 0.97,
    "report_ref": "cas://sha256/..."
  },
  "lineage": {
    "id": "lin_abc123",
    "status": "verified",
    "compact_summary_ref": "/api/v1/lineage/lin_abc123"
  },
  "access": {
    "classification": "public",
    "pii_tier": "none",
    "redaction": "none"
  },
  "time": {
    "valid_at": "2026-04-15T12:00:00Z",
    "tx_at": "2026-04-16T09:20:00Z",
    "branch": "main"
  },
  "replay": {
    "status": "replayable",
    "manifest_ref": "cas://sha256/..."
  },
  "gaps": []
}
```

Tests:

```bash
uv run pytest tests/fabric/test_decision_data_envelope.py -q
uv run pytest tests/fabric/test_lineage.py tests/fabric/test_quality_indicators.py -q
uv run pytest tests/runtime/http/test_lineage_routes.py tests/runtime/http/test_temporal_routes.py -q
uv run python tools/quality/validation/fabric_decision_data_coverage.py --check
```

Gate:

- Before Phase 6 closes, every Fabric-backed decision demo must render through
  a trust envelope or carry an explicit transitional waiver in the manifest.

#### Phase 7 — Branchable Bitemporal World

**Thesis:** Fabric should make policy memory feel like source control for the
world: time travel, branches, corrections, and scenario deltas are first-class.

**Deliverables**

- branch/snapshot capability endpoint;
- world correction and revocation semantics;
- branch merge governance evidence;
- scenario branch contract for counterfactual layer;
- temporal index review and slow-query gate;
- Kuzu graph export parity for bitemporal facts where feasible;
- retained snapshot policy tied to classification and legal retention.

**Acceptance**

- same `valid_at`, different `tx_at` reproduces late-arriving correction
  behavior across world query, lineage, quality, and trust metadata;
- branch queries never contaminate base materialization;
- merge conflicts are typed, reviewable, and exportable;
- scenario branches cannot be mistaken for observed world state;
- snapshot GC preserves audit-tagged and legally retained artifacts.

**Preconditions**

- Phase 6 trust envelopes echo `TemporalScope`.
- Existing time-travel tests in `tests/fabric/test_world_time_travel.py` remain
  green.
- `docs/reference/fabric/time-travel.md` is updated when semantics change.
- Any scenario/counterfactual work stays labelled as scenario state, not
  observed world state.

**Execution detail**

Workstreams:

1. **F7A — Correction and revocation semantics**
   - Extend `src/polisyos/fabric/world/store/segments.py` and
     `src/polisyos/fabric/world/store/emit.py` only additively.
   - Add explicit mutation kinds: `assertion`, `correction`, `revocation`,
     `branch_assertion`, `scenario_assertion`.
   - Preserve append-only history; corrections never overwrite prior facts.
   - Require provenance for correction source and correction reason.

2. **F7B — Branch governance**
   - Extend `src/polisyos/fabric/world/store/snapshots.py` with governance
     evidence for branch creation, branch head update, merge, conflict
     resolution, and branch deletion.
   - Add `schemas/fabric/world_branch.schema.json`.
   - Require merge strategy, actor, reason, target branch, source branch,
     conflict summary, and retained audit ref.

3. **F7C — Scenario branch contract**
   - Add `schemas/fabric/scenario_branch.schema.json`.
   - Scenario branches require `ScenarioRef`, assumption lineage, model/source
     lineage, validity window, and clear observed-vs-simulated marker.
   - Scenario values must not satisfy observed-world queries unless explicitly
     requested.

4. **F7D — Temporal capability and index review**
   - Extend Runtime temporal capabilities to list supported tables, unsupported
     surfaces, valid/tx range, branch support, snapshot support, and nearest
     event points.
   - Add slow-query evidence for valid-time and tx-time filters.
   - Document required indexes for DuckDB and any future adapters.

5. **F7E — Kuzu and graph parity**
   - Extend `src/polisyos/fabric/world/materialize/kuzu.py` only where temporal
     graph semantics are clear.
   - If full bitemporal graph traversal is not yet proven, expose a typed
     `graph_temporal_scope = partial` capability and link to research track R3.

6. **F7F — Retention and deletion**
   - Extend `src/polisyos/fabric/security/retention.py` with snapshot/branch
     retention classes.
   - Confidential or legally retained snapshots require encryption metadata.
   - Deletion/redaction must record impact on replay and time travel.

Mutation sketch:

```jsonc
{
  "mutation_kind": "correction",
  "fact_ref": "world.fact:abc",
  "corrects_fact_ref": "world.fact:old",
  "valid_time": {
    "valid_from": "2024-01-01T00:00:00Z",
    "valid_to": null
  },
  "tx_time": "2026-04-26T10:00:00Z",
  "reason": "late_arriving_source_revision",
  "source_evidence_refs": ["cas://sha256/..."],
  "lineage_ref": "lin_correction_123",
  "actor": "fabric.ingestion.worldbank"
}
```

Tests:

```bash
uv run pytest tests/fabric/test_world_time_travel.py -q
uv run pytest tests/fabric/test_world_materialization.py -q
uv run pytest tests/fabric/test_world_branch_governance.py -q
uv run pytest tests/fabric/test_world_temporal_capabilities.py -q
```

Gate:

- Phase 7 cannot close if the same URL/TemporalScope produces different
  values, quality status, or lineage summary across replay.
- Any partial Kuzu temporal support must be labelled in capability responses.

#### Phase Gates and Parallelization

| Gate | Must be true before moving on |
| ---- | ----------------------------- |
| Phase 0 -> Phase 1 | Inventory manifest exists, report-only validator runs, docs page generated. |
| Phase 4 -> Phase 5 | P0/P1 remediation has direct tests or accepted-risk records. |
| Phase 5 -> Phase 6 | SourceContract v2 exists for decision-demo sources and new source onboarding is gated. |
| Phase 6 -> Phase 7 | Fabric decision envelopes can carry quality, lineage, access, replay, and temporal scope together. |
| Phase 7 -> Phase 8 | Bitemporal branch/correction semantics are reproducible through tests. |
| Phase 8 -> Phase 9 | Processing guarantees are labelled and streaming/CDC paths cannot bypass trust metadata. |
| Phase 9 -> Phase 10 | Discovery/entity intelligence has evaluation fixtures and cannot overwrite canonical facts without governance. |

Parallelization:

- Phase 0 inventory can run immediately.
- Phase 1-4 should follow remediation priority, but docs/reference updates can
  run in parallel with implementation.
- Phase 5 source contracts and Phase 6 envelope design can be designed in
  parallel, but Phase 6 cannot close until Phase 5 covers demo sources.
- Phase 7 scenario branch contracts can be drafted in parallel with Phase 6,
  but implementation waits for trust envelopes and temporal echo.
- Wave R research can start immediately, but production guarantees remain
  capped until promotion criteria are met.

#### Phase 8 — Streaming and Scale Semantics

**Thesis:** Fabric must be honest about runtime guarantees. Best-in-class is not
always exactly-once. Best-in-class is knowing exactly what guarantee each path
has and surfacing it as a contract.

**Deliverables**

- processing guarantee enum:
  - `batch_atomic`;
  - `at_least_once`;
  - `at_least_once_with_dedupe`;
  - `effectively_once`;
  - `exactly_once_narrow`;
  - `replay_only`;
- idempotency and dedupe key policy;
- CDC schema-change compatibility handling;
- backpressure contract;
- distributed execution adapter interface;
- benchmark suite for ingestion, stream windows, materialization, and query;
- scale-out design ADR.

**Acceptance**

- no streaming path claims exactly-once without atomic input/state/output proof;
- out-of-order handling is explicit: wait, reorder, watermark, drop, or
  quarantine;
- dedupe windows and replay retention are visible in source contracts;
- benchmark reports include p50/p95/p99, memory, and correctness counters;
- distributed execution cannot bypass lineage, quality, access, or replay.

#### Phase 9 — Discovery and Entity Intelligence

**Thesis:** AI-assisted discovery is useful only when it is explainable,
reversible, stale-aware, and contract-bound.

**Deliverables**

- semantic catalog reference page;
- embedding-backed search with deterministic lexical fallback;
- stale embedding invalidation on schema/metadata/source-contract changes;
- NL-to-dataset resolution as ranked explainable plan;
- probabilistic entity-resolution store;
- entity override provenance and audit trail;
- Kuzu graph reasoning helpers for source overlap, conflict neighborhoods,
  source-to-policy impact, and entity neighborhoods;
- relevance and false-positive evaluation set.

**Acceptance**

- semantic search returns ranked candidates with evidence, source contract,
  profile, quality, and access state;
- entity matches are explainable, reversible, and never overwrite canonical
  facts without merge governance;
- stale embeddings are not used silently;
- graph reasoning answers origin, overlap, conflict, and downstream impact
  questions on multi-source fixtures.

#### Phase 10 — Product/API Integration Closeout

**Thesis:** Fabric is best-in-class only when downstream systems cannot
accidentally bypass it.

**Deliverables**

- Runtime endpoints for lineage, temporal capabilities, source scorecards,
  quality/trust batch lookup, replay, and impact analysis;
- frontend fixtures for Quantity, Provenance-on-hover, Trust View, temporal
  scrubber, policy diff, and counterfactual layer;
- Scientist governance passes consuming Fabric quality/trust metadata;
- Scholar and Lex citation/evidence paths using Fabric provenance;
- Foundry calibration and uncertainty paths referencing Fabric quality and
  source trust where appropriate;
- compatibility shims with sunset dates.

**Acceptance**

- design Wave 2 can render provenance and trust from Fabric-backed payloads;
- Scientist decision readiness can be capped by Fabric data quality, source
  trust, stale evidence, or missing lineage;
- every compatibility bridge has owner, reason, sunset, and migration issue;
- `polisyos.fabric.__all__` remains stable or changes only through public
  surface governance.

## 9. Wave R — Fabric Research Agenda

The items below must not be implemented as strong guarantees until they have
theorem, counterexample, calibrated benchmark, or accepted narrow scope.

| Track | Research problem | Sufficient result | Unlocks |
| ----- | ---------------- | ----------------- | ------- |
| R1 | Data-quality-to-uncertainty algebra | A typed composition rule mapping missingness/freshness/drift/schema violations into uncertainty or readiness caps | Honest propagation from Fabric into Foundry/Scientist |
| R2 | Source trust calibration | Calibration method and benchmark set for source reliability, correction history, citation density, and institutional authority | Source trust scorecards and Trust View weighting |
| R3 | Bitemporal graph semantics | Formal model for valid-time/tx-time property graphs and safe temporal traversal | Kuzu bitemporal reasoning and impact analysis |
| R4 | Lineage compression and redaction | Loss-bounded graph summarization plus redaction policy preserving auditability | Fast provenance hover without leaking restricted data |
| R5 | Probabilistic entity resolution under policy data | Evaluation protocol, uncertainty model, override governance, and false-merge kill rules | Cross-source entity intelligence |
| R6 | Exactly-once/effectively-once classification | Contract language and proof obligations for batch, CDC, replay, dedupe, and distributed execution | Honest streaming guarantees |
| R7 | Semantic schema compatibility | Method for distinguishing technical compatible changes from meaning-changing compatible-looking changes | Better schema governance |
| R8 | Adversarial open-data robustness | Threat model and fixtures for poisoned records, schema poisoning, malicious metadata, and source spoofing | Higher-trust public-data ingestion |
| R9 | Privacy-preserving provenance | Redaction and access-control model that preserves enough lineage for audit while hiding restricted values | Safe Trust View for confidential datasets |
| R10 | Policy-world replay minimality | Minimal artifact set needed to reproduce decision-bearing outputs without re-fetching external sources | Smaller retained snapshots and portable audit bundles |

Research artifacts enter as `FrontierSketch`-like evidence with capped
readiness. They do not unlock production guarantees until promotion criteria
are machine-checkable.

### Research Track Cards

#### R1 — Data-Quality-to-Uncertainty Algebra

**Open problem:** Fabric quality signals are heterogeneous: missingness,
freshness, coverage, schema drift, anomalies, source reliability, and contract
violations do not naturally compose into the same mathematical object.

**Why research-first:** A naive score-to-uncertainty mapping would make false
precision look scientific. Some defects should widen uncertainty, some should
cap readiness, and some should block decisions outright.

**Sufficient result:** A typed algebra that maps quality defects to one of:
uncertainty widening, readiness cap, hard blocker, or no decision impact, with
machine-checkable preconditions.

**Deliverable form:** theorem or calibrated empirical rulebook, counterexample
library, `QualityImpactEnvelope` contract, and governance pass fixtures.

**Unlocks:** Scientist readiness caps, Foundry uncertainty propagation, Trust
View quality explanations.

**Kill rule:** If a quality signal cannot be justified as uncertainty, it must
remain a readiness/governance signal rather than being forced into a numeric CI.

#### R2 — Source Trust Calibration

**Open problem:** Source trust is not simply institutional prestige. Correction
history, citation density, schema stability, update latency, coverage, legal
authority, and cross-source agreement all matter.

**Why research-first:** A single hand-written trust score will encode bias and
will be overread by users as policy correctness.

**Sufficient result:** Calibration protocol with gold/evaluation datasets,
confidence intervals for source trust, and explicit scope limits by source
family.

**Deliverable form:** benchmark corpus, calibration report, source-trust model
card, source scorecard contract extension.

**Unlocks:** Source trust scorecards, Trust View weighting, source selection
policy in retrieval.

**Kill rule:** If calibration data is insufficient for a source family, expose
`source_trust.calibration_status = heuristic` and cap downstream claims.

#### R3 — Bitemporal Graph Semantics

**Open problem:** Relational bitemporality is already subtle; graph traversal
with valid-time and tx-time across nodes and edges can create misleading paths
if temporal joins are underspecified.

**Why research-first:** Kuzu graph reasoning could accidentally connect facts
that were never simultaneously valid or known.

**Sufficient result:** Formal temporal graph traversal semantics with supported
query patterns, unsafe patterns, and fallback behavior.

**Deliverable form:** semantics note, query pattern catalog, counterexample
fixtures, Kuzu capability matrix.

**Unlocks:** Bitemporal graph impact analysis, source conflict neighborhoods,
entity graph reasoning over time.

**Kill rule:** Unsupported graph traversals must return `temporal_graph_partial`
or fail closed, not silently degrade to current-time graph traversal.

#### R4 — Lineage Compression and Redaction

**Open problem:** Full provenance graphs are too large for hover and may expose
restricted nodes, but summaries can hide exactly the audit edge that matters.

**Why research-first:** Graph summarization and redaction need preservation
criteria. Otherwise compact lineage becomes decorative.

**Sufficient result:** Loss-bounded summarization policy that preserves origin,
critical transforms, verification, disputed nodes, and restricted-node
placeholders.

**Deliverable form:** summarization algorithm, redaction policy, privacy tests,
golden compact/full graph parity fixtures.

**Unlocks:** Fast provenance hover, confidential Trust View, shareable audit
bundles.

**Kill rule:** If a compact summary cannot preserve audit-critical edges, UI
must show "summary incomplete" and force full authorized deep dive.

#### R5 — Probabilistic Entity Resolution Under Policy Data

**Open problem:** Government and policy data often uses unstable names, codes,
jurisdictional changes, multilingual labels, and many-to-many administrative
entities.

**Why research-first:** False merges can corrupt world state more badly than
missed matches.

**Sufficient result:** Evaluation protocol with false-merge/false-split costs,
uncertainty model, reversible candidate store, and human override governance.

**Deliverable form:** benchmark fixtures, candidate schema, scoring model,
override audit workflow, kill rules by confidence band.

**Unlocks:** Cross-source entity intelligence, graph reasoning, better conflict
detection.

**Kill rule:** Entity matches above automation threshold may suggest joins, but
canonical fact writes require confidence, evidence, and override policy.

#### R6 — Exactly-Once / Effectively-Once Classification

**Open problem:** Fabric has batch, streaming, CDC, replay, CAS, materialization,
and downstream writes. Exactly-once requires atomicity across input progress,
state update, and output write, which not every path can provide.

**Why research-first:** Overclaiming exactly-once creates false operational
safety. Underclaiming hides useful guarantees.

**Sufficient result:** Processing-guarantee contract with proof obligations and
fixtures for failure modes.

**Deliverable form:** guarantee taxonomy, model scenarios, crash/retry tests,
dedupe-window rules.

**Unlocks:** Honest streaming/CDC contracts, scale-out execution, source SLOs.

**Kill rule:** Any path lacking atomic input/state/output proof must use
`at_least_once`, `at_least_once_with_dedupe`, or `effectively_once`, not
`exactly_once_narrow`.

#### R7 — Semantic Schema Compatibility

**Open problem:** A schema change can be technically compatible while changing
meaning: renamed measures, altered denominator, changed geography, revised
seasonality, or new imputation policy.

**Why research-first:** Standard schema diffing catches structural change, not
semantic drift.

**Sufficient result:** Semantic compatibility checklist with machine-readable
signals and human-review triggers.

**Deliverable form:** semantic diff taxonomy, metadata requirements,
counterexample library, governance gate extension.

**Unlocks:** Stronger schema governance and safer source evolution.

**Kill rule:** Compatible-looking changes that alter metric meaning require
major or semantic-version bump plus downstream impact review.

#### R8 — Adversarial Open-Data Robustness

**Open problem:** Public-data connectors can ingest poisoned records, malicious
metadata, pathological files, schema spoofing, and hostile endpoint behavior.

**Why research-first:** Threat modeling must cover source-specific protocols,
not just generic API security.

**Sufficient result:** Fabric threat model with malicious fixtures and bounded
failure behavior for each connector family.

**Deliverable form:** adversarial fixture suite, source-family threat matrix,
security acceptance checklist.

**Unlocks:** Higher-trust public-data ingestion and safer AI discovery.

**Kill rule:** Any source family without adversarial fixtures cannot be marked
`production_trusted` in source scorecards.

#### R9 — Privacy-Preserving Provenance

**Open problem:** Provenance can leak sensitive values, source identities, query
intent, or protected relationships even when result values are masked.

**Why research-first:** Redaction must preserve auditability without becoming a
side channel.

**Sufficient result:** Access-aware provenance model with redacted placeholders,
authorized expansion, and proof that compact summaries do not reveal restricted
nodes beyond policy.

**Deliverable form:** redaction semantics, tests, policy examples, Trust View
restricted-mode fixtures.

**Unlocks:** Trust View for confidential datasets, safe external audit bundles.

**Kill rule:** If provenance cannot be safely summarized, restricted users see
only verification status and request-access affordance.

#### R10 — Policy-World Replay Minimality

**Open problem:** Full replay may require large raw artifacts, external source
state, schemas, transforms, quality reports, model config, and branch metadata.
Keeping everything forever is expensive and may conflict with retention policy.

**Why research-first:** Minimal replay bundles must be proven sufficient for
decision-bearing reproduction.

**Sufficient result:** Minimal artifact set by source family and world pipeline
type, with reproduction proof and known non-replayable exceptions.

**Deliverable form:** replay-minimality theorem or empirical certificate,
bundle schema, reproduction test suite, retention tradeoff note.

**Unlocks:** Portable audit bundles, smaller retained snapshots, long-term
reproducibility.

**Kill rule:** If a result cannot be reproduced from retained artifacts, its
trust envelope must say `non_replayable` with reason and retention context.

## 10. Machine-Checkable Contracts

| Contract | Location | Gate |
| -------- | -------- | ---- |
| Fabric best-in-class manifest | `tools/quality/validation/fabric_best_in_class_manifest.json` | report-only, then fail-closed per phase |
| Source contract schema | `schemas/fabric/source_contract.schema.json` | source onboarding CI |
| Quality contract schema | `schemas/fabric/quality_contract.schema.json` | connector and data-plane CI |
| Lineage event schema | `schemas/fabric/lineage_event.schema.json` | ABI snapshot check |
| Trust envelope schema | `schemas/fabric/trust_envelope.schema.json` | Runtime/OpenAPI codegen |
| Replay fixture manifest | `schemas/fabric/replay_manifest.schema.json` | record/replay CI |
| Processing guarantee contract | `schemas/fabric/processing_guarantee.schema.json` | streaming/CDC CI |
| Entity resolution candidate schema | `schemas/fabric/entity_candidate.schema.json` | ER evaluation gate |
| Source scorecard schema | `schemas/fabric/source_scorecard.schema.json` | generated docs and dashboard |

## 11. SLOs and Metrics

Fabric should not track every possible metric as an SLI. It should track a
small set that maps to user trust.

| SLI | Why it matters | Initial target |
| --- | -------------- | -------------- |
| Contract compliance rate | Users need sources to match declared schema/semantics | >= 99% for production sources |
| Replay reproduction rate | Users need audit bundles to reproduce decisions | >= 99% for replayable sources |
| Lineage coverage | Users need origin and impact for decision-bearing values | 100% for decision paths |
| Freshness compliance | Users need to know if a source is stale | >= 99% by source SLA |
| Quality gate pass rate | Users need actionable quality failures | No silent poor-quality pass |
| Quarantine resolution time | Users need poison records isolated and recoverable | P95 <= 2 business days |
| Materialization staleness | Users need world tables to reflect persisted evidence | source-specific SLO |
| Temporal query correctness | Users need valid/tx reproduction | 100% fixture pass |
| Access enforcement | Users need restricted data not to leak | 0 known unauthorized disclosures |
| Compact lineage latency | UI needs hover-ready provenance | p95 <= 150 ms for batch compact lookup |

Error-budget state gates expansion:

- green: normal feature work;
- yellow: only additive/flagged changes on default Fabric paths;
- red: security fixes, P0/P1 reliability fixes, and rollback only.

## 12. Documentation Deliverables

| Doc | Purpose |
| --- | ------- |
| `docs/reference/fabric/source-platform.md` | Connector SDK, contracts, profiles, scorecards, onboarding |
| `docs/reference/fabric/catalog.md` | Semantic catalog, search, source bindings, metadata invalidation |
| `docs/reference/fabric/trust.md` | Trust envelope, source trust, quality impact, verification status |
| `docs/reference/fabric/replay.md` | Record/replay, reproducibility, audit bundles |
| `docs/reference/fabric/observability.md` | OTel spans/metrics/logs, SLIs/SLOs, error budgets |
| `docs/reference/fabric/entity-resolution.md` | Candidate store, overrides, uncertainty, governance |
| `docs/reference/fabric/processing-guarantees.md` | Batch/stream/CDC/replay semantics and labels |
| `docs/how-to/add-fabric-source.md` | Contract-first source onboarding |
| `docs/how-to/debug-fabric-lineage.md` | Origin/impact debugging workflow |
| `docs/runbooks/fabric-source-contract-violation.md` | Contract violation incident response |
| `docs/runbooks/fabric-temporal-replay-mismatch.md` | Reproduction failure incident response |

## 13. Implementation Order

1. Create the best-in-class inventory manifest in report-only mode.
2. Wire manifest checks into current Fabric reference docs.
3. Finish P0/P1 remediation from `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`.
4. Add source contract expansion: semantics, security, quality, SLA, owner,
   terms, replay, source trust.
5. Add quality/trust references to decision-facing Fabric outputs.
6. Add Runtime batch adapters for lineage, quality, trust, and temporal scope.
7. Make world correction/branch/scenario semantics explicit.
8. Add processing-guarantee labels to streaming/CDC paths.
9. Add semantic catalog and entity-resolution only after contracts and replay
   are stable.
10. Close with downstream no-bypass gates and design Wave 2 fixtures.

## 14. Acceptance Criteria

The plan can move from `active/` to `accepted/` when:

- owner review approves the product laws and phase boundaries;
- required ADRs are listed for irreversible changes;
- machine-checkable contract files are named and scoped;
- Wave 1 work is tied to `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`;
- Wave 2 dependencies on `DESIGN_BEST_IN_CLASS_PLAN.md` are explicit;
- Wave R research tracks have promotion criteria;
- no phase depends on unbounded AI discovery or ungoverned source ingestion;
- every public behavior change has a reference-doc destination.

The program is complete when:

- all production source paths have contract, profile, quality, access, lineage,
  replay, and owner metadata;
- all decision-bearing Fabric exports use typed trust envelopes;
- bitemporal reproduction works across values, quality, lineage, and world
  state;
- source scorecards, quality reports, lineage graphs, and replay manifests are
  generated and current;
- downstream systems cannot consume Fabric decision data without trust metadata
  or an explicit transitional waiver;
- research-first guarantees are either promoted with evidence or visibly capped.

## 15. Risks

| Risk | Mitigation |
| ---- | ---------- |
| The plan duplicates the remediation plan | Treat remediation as Wave 1 dependency; this plan owns best-in-class laws and downstream integration. |
| Too much metadata slows every query | Compact summaries, batch endpoints, lazy full graph, cache keys that include temporal scope, and bounded graph expansion. |
| Lineage becomes decorative | Decision data envelope carries lineage, quality, time, and trust as one atom; coverage report exposes gaps. |
| Exactly-once claims overreach | Processing guarantee contract requires proof obligations and supports honest weaker labels. |
| AI discovery introduces false confidence | Search returns ranked candidates with evidence and stale-state metadata; no hidden direct selection. |
| Confidential data leaks through provenance | Redaction policies and access-aware lineage summaries are required before Trust View for restricted sources. |
| Schema compatibility misses semantic drift | Add semantic compatibility research track and require owner-reviewed migration evidence for meaning-changing fields. |
| Snapshot retention conflicts with privacy/deletion | Retention policy is tied to classification, legal basis, and redaction/delete workflow. |

## 16. Owner Matrix

| Area | Primary owner | Reviewers |
| ---- | ------------- | --------- |
| Source platform | `@fabric-owners` | `@platform-owners`, source owner |
| Evidence/CAS/replay | `@fabric-owners` | `@platform-owners`, security |
| Schema contracts | `@fabric-owners` | `@ir-owners`, `@runtime-owners` |
| Quality/trust | `@fabric-owners` | `@scientist-owners`, governance |
| Bitemporal world | `@fabric-owners` | `@runtime-owners`, DBA |
| Lineage/provenance | `@fabric-owners` | `@frontend-owners`, `@runtime-owners` |
| Access/retention | `@fabric-owners` | security, compliance |
| Entity intelligence | `@fabric-owners` | `@scholar-owners`, `@lex-owners` |
| Design integration | `@frontend-owners` | `@fabric-owners`, `@runtime-owners` |

## 17. First PR Slice

The first implementation PR should be deliberately small:

1. add `fabric_best_in_class_manifest.json` with manual initial statuses;
2. add validator skeleton that reports missing/partial/implemented surfaces;
3. add `docs/reference/fabric/best-in-class-inventory.md`;
4. link the inventory from `docs/reference/fabric/index.md`;
5. keep the gate report-only.

That PR creates the measurement spine. Every later phase can then ratchet
specific cells from `missing` to `implemented` without arguing from prose.
