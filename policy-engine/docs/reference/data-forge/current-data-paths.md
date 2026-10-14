# Current Data Forge paths

Owner: @data-forge-owners
Last updated: 2026-10-14
Source of truth: implementation inspected at repository pin `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`. Source and test references below are repository paths/symbols at that pin.
Verification: source and named test files were inspected; this documentation review did not run tests.

This page traces the paths that exist today. Data Forge has several domain-owned batch pipelines and selected lazy runtime APIs. Shared planning and artifact contracts do not, by themselves, mean that every domain has a common executor, persistent schema lifecycle, or automatic source-acquisition loop.

## Acquisition paths

The general requirement path starts with `polisyos.data_requirement.compiler.DataRequirementCompiler`, which compiles claim/facet obligations into a versioned `DataRequirementSpec`. Its scope and time role, quality minima, missingness and transformation tolerances, and lineage requirements define a gap denominator and source-selection preconditions. The authority boundary in `policy-engine/src/polisyos/data_requirement/_impl/models.py` explicitly does not make a requirement into source-contract binding, claim support, legal authority, method validity, or publication/closeout authority.

Runtime acquisition is bounded and owner-mediated:

1. `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py` plans eligible work from requirement gaps. `plan_evidence_acquisition` accepts an optional VOI report. The planner records VOI ranks even for ineligible entries, then filters by eligibility before recommendation; among eligible strategies with VOI records, the higher-ranked option can be recommended.
2. `run_acquisition_closed_loop` calls `plan_requirement_gap_acquisition` without a VOI report, then asks an explicit acquisition-owner gateway for artifacts. The default `RecordedAcquisitionOwnerGateway(artifacts_by_requirement={})` is offline and returns no acquired domain evidence.
3. Returned artifacts are journaled, admitted, projected into the selected world, and used to compute affected-region and grounding revalidation. The loop's authority boundary is recorded in the same module.

The closed-loop gap is **`implemented_but_not_orchestrated` for VOI-ranked acquisition**: the planner accepts an optional VOI report, but the general closed-loop call omits it. The default gateway is recorded-only and does not itself acquire domain data. The legacy `AcquisitionPlanner` adapter handles named missing distributions with its own costed plan; that is not evidence of universal source selection.

Two domain-owned examples have narrower acquisition behavior:

- Academic `policy-engine/src/polisyos/data_forge/domains/academic/batch/demand_harvest.py` reads a runtime backlog, retains supported priority classes, queries OpenAlex, writes JSONL, and records a stage manifest. This is a targeted literature harvest route, not a general acquisition scheduler.
- Catalog selection in `policy-engine/src/polisyos/data_forge/domains/catalog/selection.py` applies a source-run profile and wave, then resolves required seed dependencies. `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/acquisition_authority.py` resolves catalog authority against the baseline catalog and L5 measurement registry; it does not self-mint source, license, or L5 authority.

## Domain materialization owners

| Domain | Observed producer path | Evidence and boundary |
| --- | --- | --- |
| Academic | `policy-engine/src/polisyos/data_forge/domains/academic/batch/pipeline.py` selects harvest, parse, extraction/finalization, deduplication, optional injected Scientist claim adjudication, conflict resolution, graph/index, synthesis, scoring, QC, and publish stages. | `policy-engine/src/polisyos/data_forge/domains/academic/batch/publish.py` writes a publish manifest. Demand harvest is optional and domain-specific. |
| Catalog | `policy-engine/src/polisyos/data_forge/domains/catalog/batch/pipeline.py` selects harvest, normalize, deduplication, graph/index, core-source ingestion, embedding, benchmark, QC, and publish. | Resume inputs include basis/rule version and output inventories; publish checks `consumer_ready` before writing its manifest. |
| Legal | `policy-engine/src/polisyos/data_forge/domains/legal/batch/pipeline.py` runs configured parsing/structure/SPO extraction, quote grounding/reference resolution, graph, quality/QC, then publishes a bundle. | The runtime legal surface also exposes batch execution entrypoints; it is not purely read-only. Legal effective/publication dates have their own resolution and warning behavior. |
| Ukraine | `policy-engine/src/polisyos/data_forge/domains/ukraine/orchestrator.py` dispatches `STAGE_BUILDERS`, checks prerequisites and outputs, and writes a typed `BuildRunManifest`. | Source manifests record input/output hashes and sizes, run/stage times, and warnings. Demography source inventory is opt-in; candidates are not independently verified owner facts. |

These are domain compositions, not a universal list of policy-domain templates. External domains are registered through the domain entrypoint mechanism described in `policy-engine/src/polisyos/data_forge/domains/README.md`; their existence does not imply that all domain lifecycle capabilities are equivalent.

The shared asset kernel in `policy-engine/src/polisyos/data_forge/kernel/pipeline/assets.py` and `policy-engine/src/polisyos/data_forge/kernel/pipeline/materialize.py` defines asset specs and materialization callables. `plan_asset_specs` orders dependencies and rejects missing dependencies and cycles. It does not provide a generic executor/persisted-output bridge. A universal materialization runner is therefore **`implemented_but_not_orchestrated`** at this kernel level; domain pipelines perform their own orchestration.

## Artifact, provenance, schema, and time

`policy-engine/src/polisyos/data_forge/kernel/artifacts.py` defines `ArtifactRef` with snapshot-qualified URI and content hash, producer/version, config hash, trace/span, ownership/license/regeneration metadata, PII and retention fields, freshness SLA, and schema ID/version. Pipeline manifest helpers in `policy-engine/src/polisyos/data_forge/kernel/pipeline/manifests.py` preserve legacy raw/stage/publish forms with payload digests, fetch time/filters/parser version, stage time/status/hashes, and publish time/artifacts/QC.

Snapshot finalization in `policy-engine/src/polisyos/data_forge/kernel/snapshot/finalize.py` consumes configured publish manifests and writes snapshot binding/provenance manifests. `policy-engine/src/polisyos/data_forge/_impl/provenance_manifest.py` exposes official snapshot answers with `satisfied`, `blocked`, and `not_found` statuses. Rows bind hashes, lineage, quality gates, builder revision, transform lineage, and claim requirements. Runtime admission/consumption is exercised by `policy-engine/src/polisyos/runtime/quality/data_forge_binding.py` and its tests.

Time is domain-specific. A freshness SLA is not a substitute for source publication time, legal effective time, observation time, or build/stage time. Legal versioning resolves effective and publication dates and emits warnings for unresolved temporal metadata; Ukraine manifests retain run/stage times; academic source metadata includes publication time where available. Consumers must interpret the time role carried by the relevant artifact rather than infer it from a manifest timestamp.

The schema helpers in `policy-engine/src/polisyos/data_forge/kernel/schemas/registry.py` and migration registry are in-memory registries. They support registration and evolution operations, but the broader cross-domain persisted schema-version lifecycle has **`artifact_missing`**: this inspection found no shared persisted schema-version artifact or lifecycle.

## Canonicalization and alignment

Canonicalization is owned by the domain:

- Academic uses `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/canonical_resolver.py`, `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/variable_canonizer.py`, and `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/runtime_canonical_registry.py`. Resolution can produce new, fuzzy, or slug-derived candidates and pending review; normalized naming alone is not causal grounding.
- Catalog uses `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/variable_alignment.py` and `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/proxy_penalties.py`; alignment carries method, confidence, evidence, and proxy status/penalty.
- Legal canonicalizers are in `policy-engine/src/polisyos/data_forge/domains/legal/batch/canonicalizers.py`; legal temporal versioning is a separate concern.

These paths create or align candidate knowledge under their own evidence and review rules. They do not establish one cross-domain canonizer or authorize a claim merely because names match.

## Federation and streaming boundary

Federation lives in Fabric under `policy-engine/src/polisyos/fabric/connectors/federation/` (planner, ranker, composer, resolver, and evidence aggregation). Streaming lives in `policy-engine/src/polisyos/fabric/data_plane/streaming.py`, which includes subscription, recovery, checkpoint, schema binding, budget, and backpressure behavior. Relevant verification includes `policy-engine/tests/unit/fabric/connectors/test_federation.py` and `policy-engine/tests/unit/fabric/data_plane/test_streaming_runtime.py`.

These Fabric components are not a Data Forge-wide acquisition or continuous materialization runtime. An academic internal normalization/resolution stream does not establish a generic scheduler across domains. Continuous connector streaming belongs to Fabric; a Data Forge-wide streaming surface is **`surface_out_of_scope`** at this boundary. See [Fabric reference](../fabric/index.md) for the neighboring subsystem boundary.

## Runtime read surfaces and consumers

`policy-engine/src/polisyos/data_forge/read_api/surfaces.py` registers lazy surfaces for academic, catalog, legal, and Ukraine; `policy-engine/src/polisyos/data_forge/read_api/__init__.py` loads them lazily. Runtime consumers include:

- `policy-engine/src/polisyos/runtime/quality/data_forge_binding.py` for official snapshot/provenance admission;
- `policy-engine/src/polisyos/runtime/http/services/control/lex_pipeline.py` and `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py` for controlled legal/lexical pipeline work;
- `policy-engine/src/polisyos/lex/knowledge/store.py`, `policy-engine/src/polisyos/scientist/agent/knowledge_tools.py`, and `policy-engine/src/polisyos/foundry/methods/catalog/causal/literature_prior.py` for knowledge access.

The legal surface is registered and consumed, but its public-surface declaration is incomplete: `policy-engine/architecture/public_surface/contract.toml` and generated `policy-engine/docs/reference/public-surface.md` omit `polisyos.data_forge.read_api.legal`, while the code registry and runtime consumers include it. This is a **`surface_missing`** declaration gap, not evidence that the runtime implementation is absent.

The academic runtime surface `polisyos.data_forge.read_api.academic` exports `run_edge_synthesize` through the lazy facade; it resolves to `policy-engine/src/polisyos/data_forge/domains/academic/batch/edge_synthesize.py` and runs a batch stage against academic artifacts. This selected callable does not amount to a generic runtime batch executor; the inspection found no shared runtime orchestration contract covering every domain pipeline.

Import consolidation and boundary behavior are covered by `policy-engine/tests/unit/data_forge/test_phase6_read_api_consolidation.py`, `policy-engine/tests/unit/data_forge/test_phase8_shim_sunset.py`, and `policy-engine/tests/unit/data_forge/read_api/test_surfaces.py`. Snapshot provenance and acquisition paths have focused coverage in `policy-engine/tests/unit/runtime/quality/test_data_forge_binding.py`, `policy-engine/tests/unit/data_forge/test_w9c_provenance_manifest.py`, `policy-engine/tests/unit/runtime/quality/test_acquisition_planner.py`, and `policy-engine/tests/unit/runtime/quality/test_acquisition_route_loop.py`; domain-specific behavior has tests under `policy-engine/tests/unit/data_forge/domains/`.

## Capability gaps found in this inspection

| Capability claim | State | Evidence-based limit |
| --- | --- | --- |
| VOI-ranked acquisition in the general closed loop | `implemented_but_not_orchestrated` | The planner accepts a VOI report, but the closed-loop omits it and defaults to a recorded-only gateway; targeted academic and catalog acquisition paths are narrower. |
| Generic shared-kernel materialization execution and persisted outputs | `implemented_but_not_orchestrated` | The kernel plans dependency order and binds callables; domain pipelines provide their own execution. |
| Universal persisted schema/version lifecycle across domains | `artifact_missing` | The shared registry and migration registry are in-memory; no shared persisted schema-version artifact/lifecycle was found in this inspection. |
| Legal read API public-surface declaration | `surface_missing` | Runtime registry/consumers exist; contract and generated public-surface inventory omit the entrypoint. |
| Data Forge-wide continuous streaming surface | `surface_out_of_scope` | Fabric owns runtime streaming; the inspected Data Forge paths are domain builds/read surfaces, not a shared streaming surface. |

These states are scoped to the inspected implementation and tests at the source pin above. They do not imply that no domain-specific capability exists, or that a neighboring Fabric capability should be attributed to Data Forge.
