# Current Data Forge paths

Owner: @data-forge-owners
Last updated: 2026-10-14
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Source of truth: `repo:policy-engine/src/polisyos/data_requirement/compiler.py`,
  `repo:policy-engine/src/polisyos/data_requirement/_impl/models.py`,
  `repo:policy-engine/src/polisyos/runtime/quality/acquisition_planner.py`,
  `repo:policy-engine/src/polisyos/runtime/quality/generation_cycle.py`,
  `repo:policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py`,
  `repo:policy-engine/src/polisyos/runtime/quality/acquisition_route_loop.py`,
  `repo:policy-engine/src/polisyos/runtime/quality/data_forge_binding.py`,
  `repo:policy-engine/src/polisyos/data_forge/kernel/artifacts.py`,
  `repo:policy-engine/src/polisyos/data_forge/kernel/pipeline/assets.py`,
  `repo:policy-engine/src/polisyos/data_forge/kernel/pipeline/materialize.py`,
  `repo:policy-engine/src/polisyos/data_forge/kernel/pipeline/manifests.py`,
  `repo:policy-engine/src/polisyos/data_forge/kernel/schemas/registry.py`,
  `repo:policy-engine/src/polisyos/data_forge/kernel/snapshot/finalize.py`, and
  `repo:policy-engine/src/polisyos/data_forge/_impl/provenance_manifest.py`.

This declared set covers the requirement/acquisition, shared asset-planning, and snapshot-binding paths. Domain-specific sources and tests cited below are bounded evidence for their stated rows, not an exhaustive or transitive source audit.
Verification: source and named test files were inspected; this documentation review did not run tests.

The declared source set differs from the separately observed E02 commit. This page still describes its inspected source pin; its affected claims require [re-review after integration](../e02-documentation-snapshot.md#source-drift-in-handbook-maps).

This page traces the paths that exist today. Data Forge has several domain-owned batch pipelines and selected lazy runtime APIs. Shared planning and artifact contracts do not, by themselves, mean that every domain has a common executor, persistent schema lifecycle, or automatic source-acquisition loop.

## Acquisition paths

The general requirement path starts with `polisyos.data_requirement.compiler.DataRequirementCompiler`, which compiles claim/facet obligations into a versioned `DataRequirementSpec`. Its scope and time role, quality minima, missingness and transformation tolerances, and lineage requirements define a gap denominator and source-selection preconditions. The authority boundary in `policy-engine/src/polisyos/data_requirement/_impl/models.py` explicitly does not make a requirement into source-contract binding, claim support, legal authority, method validity, or publication/closeout authority.

Runtime acquisition is bounded and owner-mediated:

1. `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py` plans eligible work from requirement gaps. `plan_evidence_acquisition` accepts an optional VOI report. The planner records VOI ranks even for ineligible entries, then filters by eligibility before recommendation; among eligible strategies with VOI records, the higher-ranked option can be recommended.
2. `run_acquisition_closed_loop` in `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py` calls `plan_requirement_gap_acquisition` without a VOI report, then asks its configured owner gateway for artifacts. A direct call defaults to `RecordedAcquisitionOwnerGateway(artifacts_by_requirement={})`, which is offline and returns no acquired domain evidence.
3. `GenerationCycle._run_n7_acquisition_if_requested` supplies `_n7_owner_gateway`: a request-hinted or injected gateway, or `RealAcquisitionOwnerGateway` when runtime scope permits. Production scope without the promotion runtime has no default gateway and fails with `n7_runtime_store_not_supplied`. The default real gateway also leaves OpenAlex network use disabled; if explicitly enabled, `_capture_openalex` currently makes a fixed `title.search:"policy"` request for at most one work. This narrow capture is not requirement-specific retrieval and does not itself establish gap coverage or claim support.
4. The separate `producer_pipeline._requirement_gap_acquisition_report` path accepts and passes a VOI report to planning, but only returns a serialized plan; it does not invoke an acquisition gateway.
5. Returned artifacts are journaled and admitted; only accepted outputs can be projected into the selected world. The loop records rejections/no-results as well and computes affected-region and grounding revalidation. Its authority boundary is recorded in the same module.

This N7 receipt's `same_cycle_reentry` authority is scoped to that execution's local, same-cycle
projection. It is not production-native semantic-epoch admission or durable production re-entry.
The production-native path is separately owned by
`policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py`: it requires an explicitly
selected tenant/cell/run/route, replayable owner evidence, native epoch admission, and a positive
measured admitted-observation delta. The route loop in
`policy-engine/src/polisyos/runtime/quality/acquisition_route_loop.py` then verifies the persisted
growth receipt, its durable event and the bound overlay re-entry receipt before appending the next
generation cycle. A locally accepted artifact or changed local `grown_world_after_ref` alone does
not establish production admission, production world growth, or production re-entry. The inspected
negative boundary test is
`policy-engine/tests/unit/runtime/quality/test_acquisition_planner.py::test_real_owner_gateway_opt_in_captures_real_fetch_custody_without_world_growth`; it was not run for this documentation update.

The closed-loop gap is **`implemented_but_not_orchestrated` for VOI-ranked acquisition**: the planner accepts an optional VOI report, but the N7 closed-loop call omits it. Its direct-call default is recorded-only; the generation-cycle caller can supply a real owner gateway under the stated scope and custody conditions. The legacy `AcquisitionPlanner` adapter handles named missing distributions with its own costed plan; that is not evidence of universal source selection.

Two domain-owned examples have narrower acquisition behavior:

- Academic `policy-engine/src/polisyos/data_forge/domains/academic/batch/demand_harvest.py` reads a runtime backlog, retains supported priority classes, queries OpenAlex, writes JSONL, and records a stage manifest. This is a targeted literature harvest route, not a general acquisition scheduler.
- Catalog selection in `policy-engine/src/polisyos/data_forge/domains/catalog/selection.py` applies a source-run profile and wave, then resolves required seed dependencies. `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/acquisition_authority.py` resolves catalog authority against the baseline catalog and L5 measurement registry; it does not self-mint source, license, or L5 authority.

Academic retrieval and grounding are separate steps. `polisyos.ir.analytics.literature.validate_openalex_source_bound_candidate` rederives a candidate from selected OpenAlex bytes and its query, but its typed result keeps both `semantic_support` and `source_snapshot_authenticity` at `not_established`. The publication path `polisyos.ir.analytics.literature.validate_causal_claim_span_grounding` resolves the span to those bytes and calls `polisyos.scientist.validation.citation_faithfulness.evaluate_span_claim_entailment`; an unavailable configured judge abstains. Source-bound custody therefore does not by itself prove entailment or scientific correctness.

## Domain materialization owners

| Domain | Observed producer path | Evidence and boundary |
| --- | --- | --- |
| Academic | `policy-engine/src/polisyos/data_forge/domains/academic/batch/pipeline.py` selects harvest, parse, extraction/finalization, deduplication, optional injected Scientist claim adjudication, conflict resolution, graph/index, synthesis, scoring, QC, and publish stages. | `policy-engine/src/polisyos/data_forge/domains/academic/batch/publish.py` writes a publish manifest. Demand harvest is optional and domain-specific. |
| Catalog | `policy-engine/src/polisyos/data_forge/domains/catalog/batch/pipeline.py` selects harvest, normalize, deduplication, graph/index, core-source ingestion, embedding, benchmark, QC, and publish. | Resume inputs include basis/rule version and output inventories; publish checks `consumer_ready` before writing its manifest. |
| Legal | `policy-engine/src/polisyos/data_forge/domains/legal/batch/pipeline.py` runs configured parsing/structure/SPO extraction, quote grounding/reference resolution, graph, quality/QC, then publishes a bundle. | The runtime legal surface also exposes batch execution entrypoints; it is not purely read-only. Legal effective/publication dates have their own resolution and warning behavior. |
| Ukraine | `policy-engine/src/polisyos/data_forge/domains/ukraine/orchestrator.py` dispatches `STAGE_BUILDERS`, checks prerequisites and outputs, and writes a typed `BuildRunManifest`. | Source manifests record input/output hashes and sizes, run/stage times, and warnings. Demography source inventory is opt-in; candidates are not independently verified owner facts. |

These are domain compositions, not a universal list of policy-domain templates. External domains are registered through the domain entrypoint mechanism described in `policy-engine/src/polisyos/data_forge/domains/README.md`; their existence does not imply that all domain lifecycle capabilities are equivalent.

For Catalog stage reuse, the actionable currentness owner is
`policy-engine/src/polisyos/data_forge/domains/catalog/batch/material_inputs.py`, with its
invalidation rules summarized in
`policy-engine/src/polisyos/data_forge/domains/catalog/batch/README.md`. That basis snapshots
selected local configuration and assets; documented same-ID or byte changes invalidate covered
stage receipts, while mtime-only changes do not. It excludes remote response/version identity,
raw observation-corpus changes, and complete effective header policy. This is a bounded Catalog
producer rule, not a Data Forge-wide freshness guarantee. Curated default-resource packaging has a
separate owner in `policy-engine/src/polisyos/data_forge/domains/catalog/_resources.py` and is
described in [Catalog default resources](catalog-default-resources.md).

The shared asset kernel in `policy-engine/src/polisyos/data_forge/kernel/pipeline/assets.py` and `policy-engine/src/polisyos/data_forge/kernel/pipeline/materialize.py` defines asset specs and materialization callables. `plan_asset_specs` orders dependencies and rejects missing dependencies and cycles. It does not provide a generic executor/persisted-output bridge. The shared execution bridge is therefore **`bridge_missing`** at this kernel level; domain pipelines perform their own orchestration.

## Artifact, provenance, schema, and time

`policy-engine/src/polisyos/data_forge/kernel/artifacts.py` defines `ArtifactRef` with snapshot-qualified URI and content hash, producer/version, config hash, trace/span, ownership/license/regeneration metadata, PII and retention fields, freshness SLA, and schema ID/version. Pipeline manifest helpers in `policy-engine/src/polisyos/data_forge/kernel/pipeline/manifests.py` preserve legacy raw/stage/publish forms with payload digests, fetch time/filters/parser version, stage time/status/hashes, and publish time/artifacts/QC.

Snapshot finalization in `policy-engine/src/polisyos/data_forge/kernel/snapshot/finalize.py` consumes configured publish manifests and writes snapshot binding/provenance manifests. `policy-engine/src/polisyos/data_forge/_impl/provenance_manifest.py` exposes official snapshot answers with `satisfied`, `blocked`, and `not_found` statuses. Rows bind hashes, lineage, quality gates, builder revision, transform lineage, and claim requirements. Runtime admission/consumption is exercised by `policy-engine/src/polisyos/runtime/quality/data_forge_binding.py` and its tests.

Keep the evidence roles separate when routing readers. An `OfficialSnapshotAnswer` reports a
claim/requirement binding and recorded gate statuses; it is not an independent authority or
quality verifier. The finalized-manifest lookup checks the stored `SnapshotQualityGate.status`
values in `policy-engine/src/polisyos/data_forge/_impl/provenance_manifest.py`. Runtime binding in
`policy-engine/src/polisyos/runtime/quality/data_forge_binding.py` checks gate presence,
pass-like status, and artifact-reference shape; a bare reference is treated as `pass`, and the
referenced quality result is not resolved or recomputed there. The runtime claim-binding check
rejects an empty or context-only `authority_level`, but any other non-empty string passes that
check; `policy-engine/src/polisyos/data_forge/kernel/snapshot/finalize.py` defaults an omitted
level to `closeout`, and `OfficialSnapshotAnswer` does not return the level. These fields therefore
record declared binding evidence, not independently verified quality or authority substance.

Runtime snapshot binding also checks a timestamp (`published_at`, `snapshot_created_at`, or
`as_of`) against `freshness_ttl_seconds` or `max_age_seconds`; the implementation default is 90
days. That check is snapshot age, not a substitute for source publication, observation, or legal
effective time. Likewise, `ArtifactRef.freshness_sla_seconds` is an artifact contract field; its
presence alone does not show that a consumer evaluated it. The N7 receipt above carries local
`same_cycle_reentry` authority and is not a finalized official snapshot or proof of current source
data.

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

Some internal cross-package consumers also import narrowly selected domain modules directly:
`policy-engine/src/polisyos/scientist/methods/autotune/claim_adjudication_runtime.py` uses
`polisyos.data_forge.domains.academic.batch.claim_adjudicator` and
`polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier`; Foundry's
`policy-engine/src/polisyos/foundry/methods/catalog/simulation/demography.py` imports
`polisyos.data_forge.domains.ukraine.demography.source_inventory`; Scientist's
`policy-engine/src/polisyos/scientist/governance/blueprint_release.py` imports selected
`polisyos.data_forge.domains.ukraine.builders.demography` and
`polisyos.data_forge.domains.ukraine.manifests` functions, while
`policy-engine/src/polisyos/scientist/governance/calibration_validation.py` imports Ukraine
manifests. These are specific internal dependencies, not additional supported general runtime
surfaces or a shared batch contract.

### Reader routing and source-change triggers

Use this as a routing aid, not a repository-wide freshness contract. Reinspect the named owner
when that source path or its consumer changes; test references elsewhere on this page were
inspected at the pin above, not executed.

| Reader question or source change | Start with | Evidence boundary |
| --- | --- | --- |
| Which Catalog YAML default is resolved, or did its package projection change? | `policy-engine/src/polisyos/data_forge/domains/catalog/_resources.py`, `policy-engine/src/polisyos/data_forge/read_api/catalog.py`, and [Catalog default resources](catalog-default-resources.md) | Curated configuration path and packaging evidence; it does not show that external observations were refreshed. |
| Can a Catalog batch stage reuse its prior output? | `policy-engine/src/polisyos/data_forge/domains/catalog/batch/material_inputs.py` and `policy-engine/src/polisyos/data_forge/domains/catalog/batch/pipeline.py` | The stage receipt is checked against its bounded selected local-input basis; it does not bind all headers or remote response versions. |
| What does quality or readiness establish? | Domain quality owners such as `policy-engine/src/polisyos/data_forge/domains/catalog/quality.py`, `policy-engine/src/polisyos/data_forge/domains/academic/quality.py`, and the [Fabric quality reference](../fabric/quality.md) | Domain QC/readiness and Fabric connector scoring have distinct owners. A passing readiness result is not itself a source-time or snapshot-age check. |
| Did a domain producer run and publish these artifacts? | The selected producer in the [Domain materialization owners](#domain-materialization-owners) table, `policy-engine/src/polisyos/data_forge/kernel/pipeline/manifests.py`, and its domain `publish.py` | Stage and publish manifests describe the producer run and outputs; inspect that producer's source inputs and time roles for freshness. |
| Is a published snapshot bound for a claim requirement, and is its binding within its configured age? | `policy-engine/src/polisyos/data_forge/kernel/snapshot/finalize.py`, `policy-engine/src/polisyos/data_forge/_impl/provenance_manifest.py`, and `policy-engine/src/polisyos/runtime/quality/data_forge_binding.py` | Official snapshot provenance and runtime binding are separate from N7's locally accepted acquisition receipt; a binding-age pass does not prove source-observation recency. |

Import consolidation and boundary behavior are covered by `policy-engine/tests/unit/data_forge/test_phase6_read_api_consolidation.py`, `policy-engine/tests/unit/data_forge/test_phase8_shim_sunset.py`, and `policy-engine/tests/unit/data_forge/read_api/test_surfaces.py`. Snapshot provenance and acquisition paths have focused coverage in `policy-engine/tests/unit/runtime/quality/test_data_forge_binding.py` and `policy-engine/tests/unit/data_forge/test_w9c_provenance_manifest.py`; their fixture-backed answers do not establish independent gate-result or authority verification. Other named coverage includes `policy-engine/tests/unit/runtime/quality/test_acquisition_planner.py::test_voi_ranking_is_filtered_by_eligibility_before_recommendation`, `policy-engine/tests/unit/runtime/quality/test_acquisition_source_replay.py`, `policy-engine/tests/unit/ir/test_literature_openalex_grounding.py`, `policy-engine/tests/unit/data_forge/domains/academic/knowledge/test_openalex_skg_ingest.py`, `policy-engine/tests/unit/data_forge/domains/academic/batch/test_article_extractor.py`, `policy-engine/tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py`, and `policy-engine/tests/unit/data_forge/domains/academic/knowledge/test_claim_occurrence_vocabulary_transport.py`. Domain-specific behavior also has tests under `policy-engine/tests/unit/data_forge/domains/`. These test sources were inspected but not executed.

## Capability gaps found in this inspection

| Capability claim | State | Evidence-based limit |
| --- | --- | --- |
| VOI-ranked acquisition in the general closed loop | `implemented_but_not_orchestrated` | The N7 loop omits VOI; its direct-call default is recorded-only, while the generation-cycle path supplies a real gateway only under its scope/custody conditions. OpenAlex network use is disabled by default, and its enabled capture is a fixed one-work query. |
| Generic shared-kernel materialization execution and persisted outputs | `bridge_missing` | The kernel plans dependency order and binds callables; it supplies no generic execution/persistence bridge, so domain pipelines provide their own execution. |
| Universal persisted schema/version lifecycle across domains | `artifact_missing` | The shared registry and migration registry are in-memory; no shared persisted schema-version artifact/lifecycle was found in this inspection. |
| Legal read API public-surface declaration | `surface_missing` | Runtime registry/consumers exist; contract and generated public-surface inventory omit the entrypoint. |
| Data Forge-wide continuous streaming surface | `surface_out_of_scope` | Fabric owns runtime streaming; the inspected Data Forge paths are domain builds/read surfaces, not a shared streaming surface. |

These states are scoped to the inspected implementation and tests at the source pin above. They do not imply that no domain-specific capability exists, or that a neighboring Fabric capability should be attributed to Data Forge.
