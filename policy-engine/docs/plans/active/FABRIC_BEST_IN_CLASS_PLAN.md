---
title: Fabric Best-in-Class Plan
status: active
owner: fabric-owners
created: 2026-04-26
last_verified: 2026-04-28
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

As of 2026-04-28, Wave 2 strict closure treats Wave R as a true research
boundary, not as a place to hide unfinished production work.

Current machine-checkable state:

- `tools/quality/validation/fabric_wave2_strict_closure.py --check` passes.
- All non-R Wave 2 inventory surfaces are `implemented` or `not_applicable`.
- All 20 production-visible SourceContract v2 records have replay fixtures,
  field-level access policies, profile, quality, lineage, retention, owner,
  reviewer, SLO, scorecard, and generated docs evidence.
- `world.future_table_snapshot_adapters` is `not_applicable` for Wave 2 because
  Iceberg/Delta-style adapters are metadata-only and runtime create/query paths
  fail closed.
- The only R-excluded inventory surfaces are:
  - `world.kuzu_temporal_scope_capability`: `partial`;
  - `world.temporal_graph_reasoning`: `blocked_by_research`.

The items below must not be implemented as strong guarantees until they have a
theorem, counterexample set, calibrated benchmark, or accepted narrow scope.
Production paths may use heuristic, partial, or narrow labels while research is
open, but they must keep those labels visible in contracts, capability
responses, scorecards, and docs.

| Track | Current production state | Research problem | Sufficient result | Unlocks |
| ----- | ------------------------ | ---------------- | ----------------- | ------- |
| R1 | Quality refs, source contracts, scorecards, and Scientist/Fabric trust gates exist | Data-quality-to-uncertainty algebra | Typed composition rule mapping missingness/freshness/drift/schema violations into uncertainty widening, readiness caps, hard blockers, or no decision impact | Calibrated propagation from Fabric into Foundry/Scientist |
| R2 | Source trust is carried as heuristic/declarative contract metadata and scorecard evidence | Source trust calibration | Calibration method and benchmark set for source reliability, correction history, citation density, coverage, latency, institutional authority, and cross-source agreement | Calibrated source trust weighting in Trust View and source selection |
| R3 | Kuzu graph helpers exist, but `graph_temporal_scope=partial`; temporal graph reasoning is blocked | Bitemporal property-graph semantics | Formal model for valid-time/tx-time property graphs, safe traversal, correction/revocation behavior, branch/scenario isolation, and DuckDB/Kuzu parity | Kuzu bitemporal reasoning and temporal impact analysis |
| R4 | Compact/full lineage APIs and exports exist; access metadata is field-level | Lineage compression and redaction | Loss-bounded graph summarization plus access-aware redaction policy preserving auditability | Faster provenance hover and safe confidential Trust View |
| R5 | Probabilistic entity store, explainable candidates, overrides, and merge governance exist | Entity resolution risk calibration under policy data | Evaluation protocol, uncertainty model, false-merge/false-split cost model, and longitudinal administrative-boundary fixtures | Safer cross-source entity intelligence |
| R6 | Processing guarantee enum, dedupe/backpressure contracts, and validators exist | Exactly-once/effectively-once proof obligations for distributed execution | Contract language and proof fixtures for atomic input progress, state update, output write, replay, dedupe, and adapter boundaries | Promotable `exactly_once_narrow` claims where proof exists |
| R7 | Schema evolution, semantic IDs, units, normalization, and governance gates exist | Semantic schema compatibility beyond structural diffing | Method for detecting meaning-changing compatible-looking changes and forcing owner/reviewer/migration evidence | Stronger schema governance for high-impact sources |
| R8 | Security/integrity hardening and malicious fixtures exist for current paths | Adversarial open-data robustness | Source-family threat model and adversarial fixture corpus for poisoning, spoofing, malicious metadata, and hostile endpoints | Higher-trust public-data ingestion labels |
| R9 | Field-level access policies, masking, PII, retention, and audit surfaces exist | Privacy-preserving provenance | Redaction/access model that preserves auditability without leaking values, source identity, query intent, or relationships | Safe external audit bundles and restricted Trust View |
| R10 | Production sources are replayable; non-replayable production reasons are disallowed | Policy-world replay minimality | Minimal artifact-set certificate by source family and world pipeline type, with reproduction proof and retention tradeoff model | Smaller portable audit bundles and longer-term reproducibility |

Research artifacts enter as `FrontierSketch`-like evidence with capped
readiness. They do not unlock production guarantees until promotion criteria
are machine-checkable.

### Promotion Protocol

Every Wave R track must move through the same promotion protocol before it can
change production claims:

1. **Research note:** problem statement, assumptions, non-goals, threat model or
   mathematical model, and explicit counterexamples.
2. **Fixture pack:** deterministic tests that include success cases, failure
   cases, and at least one adversarial or boundary case.
3. **Capability label:** current production API remains labelled `partial`,
   `heuristic`, `declared`, `effectively_once`, or `unsupported` until the gate
   is promoted.
4. **Validator:** a repository-local check that fails when the research result
   is claimed without evidence.
5. **Reference doc:** user-facing semantics and operational limits.
6. **Strict gate update:** only after the above, update the Fabric inventory and
   strict closure validator to recognize the promoted capability.

Wave R promotion must not depend on live LLM calls, live external data, or
non-deterministic network state. LLM-assisted analysis can produce drafts or
candidate hypotheses, but the promotion evidence must be replayable from
repository fixtures or pinned artifacts.

### Active R-Excluded Surfaces

The strict Wave 2 gate currently excludes only bitemporal property-graph
semantics:

| Inventory surface | Current status | Reason | Promotion target |
| ----------------- | -------------- | ------ | ---------------- |
| `world.kuzu_temporal_scope_capability` | `partial` | Kuzu exports carry temporal metadata, but full temporal traversal semantics are not proven | R3 formal semantics plus DuckDB/Kuzu parity fixtures |
| `world.temporal_graph_reasoning` | `blocked_by_research` | Temporal origin/overlap/conflict/impact reasoning can create invalid paths without formal valid/tx traversal rules | R3 capability matrix, unsafe-pattern catalog, and fail-closed query behavior |

External Iceberg/Delta/Hudi-style table-format adapters are not a Wave R
promotion target in this plan. They remain `not_applicable` for Wave 2 strict
closure unless a separate production-visible adapter roadmap is opened.

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

**Current repo anchor:** `FabricDecisionData.quality`, source scorecards,
`FabricTrustGatePass`, and the product integration validators already consume
quality/trust metadata. R1 should not recreate those gates; it should calibrate
when a quality defect becomes uncertainty widening versus readiness blocking.

**Research tasks:**

1. Define a typed `QualityImpactEnvelope` with impact classes:
   `uncertainty_widening`, `readiness_cap`, `hard_blocker`, and
   `no_decision_impact`.
2. Build a counterexample set where scalar quality scores are misleading:
   stale-but-stable, fresh-but-poisoned, complete-but-schema-shifted,
   sparse-but-decision-irrelevant, and high-quality-but-low-authority.
3. Map existing quality statuses into conservative default impacts without
   changing current production readiness behavior.
4. Produce a validator that rejects any Foundry/Scientist numeric uncertainty
   expansion unless the quality signal has a supported impact class.

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

**Current repo anchor:** SourceContract v2 carries `source_trust` with
`calibration_status`; source scorecards are generated for all 20 production
sources. R2 promotes only calibrated weighting. Heuristic source trust remains
valid as labelled metadata.

**Research tasks:**

1. Define source-family-specific calibration labels: institutional statistics,
   government portals, open-data catalogs, files/object stores, SQL/GraphQL,
   GeoJSON, and event streams.
2. Build a correction-history and schema-stability benchmark from replay
   fixtures and source contract snapshots.
3. Separate institutional authority from empirical reliability so high-authority
   sources can still be stale or schema-unstable.
4. Add confidence intervals and "insufficient calibration data" outcomes to the
   source trust model card.

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

**Current repo anchor:** DuckDB world query, branch/snapshot governance,
correction/revocation metadata, Kuzu export helpers, and discovery graph
helpers are implemented. `graph_temporal_scope=partial` is intentionally visible
in temporal capabilities. R3 is the only current production-blocking Wave R
track.

**Research tasks:**

1. Define the temporal property-graph model:
   - node valid interval;
   - edge valid interval;
   - node tx time;
   - edge tx time;
   - branch id;
   - scenario/observed-world marker;
   - correction and revocation lineage.
2. Specify path validity rules for:
   - same `valid_at`, different `tx_at`;
   - late-arriving corrections;
   - revoked facts;
   - branch assertions;
   - scenario assertions;
   - mixed observed/scenario traversal;
   - source conflict neighborhoods.
3. Build counterexample fixtures where current-time graph traversal would
   produce a false origin, false conflict, or false downstream impact.
4. Define a query-pattern catalog:
   - safe point-in-time traversal;
   - safe interval overlap traversal;
   - safe impact neighborhood;
   - unsafe temporal join;
   - unsupported scenario/observed mixing.
5. Add DuckDB/Kuzu parity fixtures that prove equivalent answers for supported
   patterns or explicit `unsupported_temporal_scope` for unsupported patterns.
6. Define capability labels: `none`, `partial`, `point_in_time`, `interval`,
   `branch_aware`, `scenario_aware`, and `full`.
7. Add a promotion validator that fails if `graph_temporal_scope` is stronger
   than the proven fixture coverage.

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

**Current repo anchor:** Runtime exposes compact/full lineage, batch lineage,
OpenLineage/PROV exports, Trust View payloads, and field-level access metadata.
R4 is about mathematically defensible compression/redaction, not about basic
lineage availability.

**Research tasks:**

1. Define audit-critical edge classes that compact summaries must preserve.
2. Define redaction placeholders that preserve graph shape without leaking
   restricted field values, source identity, or relationship details.
3. Build compact/full parity fixtures for origin, transform, quality, dispute,
   restriction, and replay edges.
4. Add benchmark targets separately for summary quality and latency.

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

**Current repo anchor:** Semantic catalog, deterministic lexical fallback,
stale invalidation, explainable ranked plans, entity candidate store, override
audit, and graph helpers are implemented. R5 promotes calibrated automation
thresholds; it must not bypass merge governance.

**Research tasks:**

1. Build longitudinal fixtures for renamed jurisdictions, split/merged
   administrative units, multilingual labels, and code reuse.
2. Define false-merge and false-split cost weights by decision context.
3. Calibrate confidence bands: suggest-only, human-review-required,
   governance-merge-eligible, and forbidden.
4. Prove that accepted entity matches cannot overwrite canonical facts without
   merge governance evidence.

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

**Current repo anchor:** Processing guarantee contracts, dedupe policies,
backpressure semantics, CDC compatibility handling, distributed trust gates, and
benchmarks already exist. R6 is limited to promoting stronger guarantees such as
`exactly_once_narrow` for specific paths.

**Research tasks:**

1. Write proof obligations for input progress, state transition, output write,
   cursor update, replay manifest update, and lineage/quality/access sidecars.
2. Build crash matrix fixtures for every boundary between those commits.
3. Define when CAS atomic writes plus idempotency are enough for
   `effectively_once` but not `exactly_once_narrow`.
4. Add adapter-level proof records for any future distributed executor.

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

**Current repo anchor:** Schema IDs, stable field IDs, contract-aware
transforms, unit handling, semantic validation, locale/Unicode normalization,
and schema-evolution tests exist. R7 focuses on semantic drift that looks
structurally compatible.

**Research tasks:**

1. Build semantic-drift counterexamples: denominator change, geography change,
   seasonality change, imputation-policy change, unit display change, and
   source methodology revision.
2. Define metadata fields that must change when semantics change.
3. Add review triggers for compatible-looking but meaning-changing diffs.
4. Explore deterministic, non-LLM heuristics first; any LLM-assisted semantic
   review must be advisory and fixture-replayable before promotion.

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

**Current repo anchor:** Security/integrity hardening covers query/filter
injection, URL/path safety, bounded JSON/decompression, safe transforms,
provenance escaping, UTC time, and finite numeric validation. R8 expands from
known malicious fixtures to systematic source-family adversarial corpora.

**Research tasks:**

1. Build adversarial fixture packs by source family:
   HTTP/open-data, file, object storage, SQL, GraphQL, GeoJSON, and event
   stream.
2. Include poisoning of records, metadata, schema, pagination, compression,
   encodings, Unicode, redirects, and rate-limit behavior.
3. Define `production_trusted` versus `production_visible` scorecard labels.
4. Add a threat matrix that maps attack class to rejection, quarantine,
   redaction, degraded fetch, or accepted-risk behavior.

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

**Current repo anchor:** SourceContract field policies, Runtime access refs,
column masking, PII staging, retention, and governance metadata are in place.
R9 promotes formal privacy-preserving provenance semantics for restricted
sharing.

**Research tasks:**

1. Define side-channel risks from graph shape, source identity, query intent,
   timestamps, and relationship neighborhoods.
2. Specify authorized expansion rules for compact summaries and full graphs.
3. Build restricted-mode Trust View fixtures for public, internal,
   confidential, regulated PII, and sensitive policy/legal signals.
4. Add noninterference-style tests where unauthorized users cannot infer a
   restricted node from summary deltas.

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

**Current repo anchor:** Strict Wave 2 requires replay fixtures for every
production-visible source and disallows production `non_replayable_reason`.
R10 optimizes retained evidence size; it must not weaken replay guarantees.

**Research tasks:**

1. Define replay-minimal artifact classes by source family:
   transcript, normalized rows, schema snapshot, source contract, quality
   report, lineage seed, branch/snapshot metadata, and transform config.
2. Produce a minimality certificate that says which omitted artifacts are
   provably unnecessary for a given replay class.
3. Add retention tradeoff fixtures for legal hold, confidential data, public
   data, and source-terms-bound artifacts.
4. Define a portable audit bundle schema that preserves replay without
   re-fetching external sources.

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
