# GY-N13b Acquisition Executor Implementation Plan

> **For agentic workers:** execute one mutating workstream at a time. Every workstream follows
> RED -> observed RED -> minimal GREEN -> focused regression -> scoped commit. Validators that
> materialize shared `.tmp` state run strictly serially.

**Goal:** Convert N7 catalog routes into fail-closed local-lift and live-fetch execution, persist the
first admitted epoch without mutating the production catalog, make the existing L1 availability read
observe that epoch, and prove one honest census-backlog outcome plus one certified derived-data case.

**Canonical design:** GY plan Rev 18,
`docs/plans/active/layer3-slices/GY-engine-subordination.md`, GY-N13b and sections 3.5.6, 3.5.7,
3.5.9, 3.5.10, 3.5.11, and 3.5.12. This document sequences the already-approved design; it does
not create a competing engine or world owner.

**Architecture:** N7 opens the canonical read-only `DatasetCatalogGraph` through the Data Forge read
API and captures exact catalog `FetchPlan` rows. A new functionally named acquisition executor
consumes one plan or one local source field at a time. Both lanes journal raw owner evidence before
classification, measure schema in quarantine, derive a complete admission passport, and admit only
passport-backed canonical observations. A Data Forge catalog-overlay owner persists immutable
epoch rows and last-mile field bindings in a separate DuckDB file, then exposes baseline-plus-overlay
union views through the existing catalog read path. The baseline remains epoch 0 and is hash-checked
before and after every run. Derived observations use content-addressed recipes and certificates and
can never enter the observed overlay.

**Tech stack:** Python 3.14, DuckDB, Parquet, existing Fabric connectors/retrieval/ingestion/CAS,
Pydantic v2 strict DTOs, existing L5 and alignment owners, pytest, Ruff, generated JSON/DuckDB
artifacts.

**Status (2026-07-17):** `in_progress`

## Landing and isolation receipt

- N13a merge-tree was clean; merge commit on main is `719d7a35a2221f681a27d69b877c6ea8d58dd6d8`.
- Audited N13a census input: commit `154f2b11b`; semantic identity
  `sha256:62c7e666c58002509c0cd3b65ac1a22630b6b55e7631df676986ab829be5f3c2`.
- Canonical L6/N8/N10/N13a provenance ripple commits:
  `986a54daa`, `6e71f9fc3`, `8eed73d7d`, `f167adb04`, `46447ae67`, `7c648b045`,
  `687545824`, and `a906ed7c1`.
- Final N10 capstone file identity:
  `sha256:92d6bcc88dc703d45cdcd5e9960974b4c9fb00f879a6295d97c95b81f35e1636`;
  contract semantic identity:
  `sha256:8deeb3f9bb26e88b60c98fc996813a4a74db3d2ee6dff777cf8f0f5bf9e6babc`.
- Final N13a census file identity:
  `sha256:5807a9cbb1541b2bd0a12771aed478f19a6672bdfbe313ad868eebee2a4a8d9a`.
- Serial Step-0 smoke passed: L6, N4, N8, N10a, composition, N10, N13a, generation-cycle
  disposition ledger, and architecture guardrails.
- Lane: `.worktrees/gy-n13b` on `codex/gy-n13b-acquisition-executor` at `a906ed7c1`.
  N10/N13a worktrees remain intact.
- Atlas isolation: never touch any Atlas worktree or `docs/brand/**`, `apps/**`,
  `docs/plans/active/atlas-slices/**`, or `architecture/atlas_surfaces/**`.

## Measured target decision

- The frozen N13a denominator is 19 cycle-demand variables: four already executable and 15
  `binding_gap` residuals. All three capstone routes are `not_a_data_gap`; their structural blockers
  are immutable control witnesses, not demonstration targets.
- The rank-1 residual `avg_hh_income_uah` has 100 calibrated household cells but no currency,
  nominal/real basis, or base-year authority. Its honest local-lift terminal is `basis_mismatch`; it
  must not be admitted merely because values exist.
- The first admissible local world-growth candidate is `cells.distress_score`: it is a measured
  N13a `binding_gap`, is demanded by the L6 world-slot projection, and the existing S1 owner already
  computes it generically from all 11,574 `corrected_firm_panels.parquet` rows via
  `corrected_exit_bias`. The world-slot owner declares unit `ratio`, and source values are bounded
  `[0,1]`. N13b will add the missing data registry edge; no per-metric branch is permitted in code.
- No census residual has a live executable binding. The live lane therefore cannot claim D2 gap
  closure. One N13a-authorized World Bank attempt for CPI/deflator data may prove live
  resolve->ingestion->passport->overlay and supply the derived-data auxiliary input, but it remains
  a plumbing/world-growth witness rather than a capstone-route closure.
- If owner validation disproves the distress mapping or the World Bank call becomes unsafe, record a
  typed deeper terminal. Do not weaken admission to force closure.

## Global constraints and stop law

- The 1.32 GiB production catalog is read-only epoch 0. Hash it before and after every acquisition.
  Any mutation is RED. No code or command writes below `production_data/**`.
- Full denominators and mappings come from catalog/source data. Connector families, fields, and
  variable edges are never hardcoded as executable code lists. Data/registry rows may name the
  measured target.
- Owner validation is fail-closed. A present string, shaped payload, catalog rank, connector/model
  self-attestation, or class-(iv) model output cannot earn admission.
- Live execution requires the N13a public harness/simulator receipt, a schema-carrying request,
  owner-derived HTTP limits, one variable, one call, append+fsync journal evidence, and progress
  heartbeats. The response is never repaired.
- CAS and `DataSnapshot` are quarantine evidence until a passport admits rows. Quarantine bytes are
  never visible through the L1 union.
- Epochs and provenance are load-bearing. Observed, proxy, and derived classes remain distinct;
  authority can only stay equal or degrade.
- The capstone route projection hash is a narrow binding. Adding adjacent rows must not change any
  route class, terminal, blocker, or support decision.
- Run targeted tests only; never full pytest/backend verify/CI parity. Run shared-scratch validators
  serially.
- Stop only for unsafe license/ToS, genuinely different-world data, required engine behavior
  changes, a corrupt/unreadable catalog class, or a gap that can close only by weakening a gate.

## Pattern pass

- Relevant failure patterns: P01/P02 (contract/thin orchestration), P04/P05/P09/P15
  (status/authority/warning/speculation), P07/P08 (replay/time roles), P10/P12/P14
  (semantic adequacy/producer handshake/evidence strength), P27/P28 (duplicate owner/unstrangled
  predecessor), and P29-P34 (behavioral proof, provenance naming, class repair, trust-by-form,
  adversarial variation, honest isolation).
- Existing defects: N7 constructs `RetrievalService` without the catalog; `_capture_fabric` imports
  and discards ingestion; counts-only retrieval currently manufactures registrations; profiles are
  metadata-only; baseline consumers open DuckDB directly; raw-variable binding edges are missing;
  and journal refs are not durable owner evidence.
- Smallest correct pattern: one catalog resolution owner, one append-only evidence journal, one
  admission passport, one immutable overlay/attachment chokepoint, one generic field-binding
  algebra, and one content-addressed derivation recipe.
- Capability labels before work: `implemented_but_not_orchestrated` (catalog plans/ingestion), plus
  `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`,
  `verification_missing`, `surface_missing`, and `semantic_test_missing` for admission/overlay.
- Acceptance signal: a content-bound requirement resolves to an exact plan or local edge, executes
  once, persists journal/CAS/passport/overlay lineage, changes the existing availability result at a
  new epoch, re-runs the demanding stage to a recomputed closure/deeper state, and survives decisive
  negative flips.

## Ownership and file map

### Runtime/Data Forge implementation

- `src/polisyos/runtime/quality/acquisition_planner.py`: N7 catalog injection, exact plan capture,
  execution handoff, and registration derivation.
- `src/polisyos/runtime/quality/acquisition_executor.py` (new, functionally named): strict execution
  request/result/passport DTOs; generic local/live lanes; measure-then-validate; CAS and lifecycle
  refs. It may import Fabric and Data Forge, but never CG/world engines.
- `src/polisyos/data_forge/domains/catalog/knowledge/overlay.py` (new): immutable overlay schema,
  epoch transactions, last-mile field bindings, baseline hash fence, and read-only union attachment.
- `src/polisyos/data_forge/read_api/catalog.py`: lazy exports for the overlay owner and shared read
  session; no second catalog API.
- `src/polisyos/runtime/quality/data_state_substrate.py`: route the existing L1 availability read
  through the shared attachment and expose epoch-aware counts without changing its public address.
- `src/polisyos/runtime/quality/generation_cycle.py`: route its direct L1 value-profile read through
  the same attachment and consume the rederived acquisition outcome.
- `src/polisyos/fabric/data_plane/evidence_journal.py` (new): extracted append+fsync owner reused by
  N13a and N13b.
- `src/polisyos/runtime/quality/derived_observations.py` (new): provenance class, certificate,
  basis checks, CAS recipe identity, and cache-hit receipt.

### Generated evidence and verification

- `architecture/policy_design_case/layer3_gy_acquisition_overlay.duckdb` (new): committed admitted
  epoch rows and field-binding registry; baseline bytes are never copied or modified.
- `architecture/policy_design_case/layer3_gy_acquisition_executor_contract.json` (new): frozen
  world-growth, passport, quarantine, route-preservation, and derivation receipt.
- `architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl` (new): bounded raw
  evidence; quarantine/lifecycle input, never a canonical observation source by itself.
- `tools/quality/validation/layer3_gy_acquisition_executor.py` and
  `check_layer3_gy_acquisition_executor.py` (new): recomputing writer/checker/flips.
- `tests/repo_quality/tools/test_layer3_gy_acquisition_executor.py` (new) plus focused owner tests.
- `docs/superpowers/journals/2026-07-17-gy-n13b-acquisition-executor.md` (new): execution ledger.
- `architecture/generated_artifacts.toml`: lifecycle registration for contract, overlay, and journal.

## Workstream 1 — Wire catalog resolution into N7 without laundering plans

- [ ] Add RED tests proving `RealAcquisitionOwnerGateway` reaches a fixture
  `DatasetCatalogGraph`, disables ExploreLane, captures full canonical `FetchPlan` rows, performs no
  execution/network write, and emits no substrate registration from plan presence.
- [ ] Add a resolver RED proving `execution_tier="catalog"` cannot become an executable plan; only
  `fetchable` and `transport_ready` pass.
- [ ] Inject the graph through `polisyos.data_forge.read_api.catalog`, resolve the canonical L1 path
  through `default_substrate_catalog_paths`, close gateway-owned graph resources, and set
  `allow_explore_fallback=False`.
- [ ] Delete the import-and-`del` probe. Preserve exact plan/candidate projections in the raw owner
  payload, but keep registrations empty until admission.
- [ ] Focused tests + Ruff. Commit: `feat: wire N7 catalog acquisition plans`.

## Workstream 2 — Consolidate journal-first execution and E7 authorization

- [ ] Extract N13a's canonical append+fsync event writer into the Fabric data plane without changing
  N13a journal bytes. Both lanes must call the same owner.
- [ ] Add RED tests for evidence-before-classification, durable raw refs, one-variable/call budgets,
  monotone heartbeats, response byte limits, and an N13a harness failure blocking execution.
- [ ] Define a strict execution authorization receipt that content-binds the N13a family receipt,
  source profile, schema-carrying request, typed HTTP limits, call budget, and baseline identity.
- [ ] Prove the existing N13a checker remains green and its artifact/journal bytes unchanged.
- [ ] Focused tests + Ruff. Commit: `feat: consolidate acquisition evidence journal`.

## Workstream 3 — Implement passport, quarantine, and immutable epoch overlay

- [ ] RED tests: baseline mutation; metadata-only schema admitted without measurement; missing
  schema/unit/license/PII/checksum/watermark/L5 tier; fake-present refs; proxy-as-exact; passport
  bypass; quarantine promotion; missing epoch; model output as observation.
- [ ] Define strict measured-profile, field-binding, passport, quarantine, epoch, and admission DTOs.
  The passport derives `admitted`, `admitted_degraded`, or `quarantined`; callers cannot pin it.
- [ ] Persist raw evidence -> measured profile -> passport in CAS. Extend existing quarantine
  persistence; do not create a competing quarantine store.
- [ ] Implement the overlay transaction with `epoch_id > 0`, source/passport/provenance refs, time
  roles, observation class, and `ds_metric_field_bindings`. Validate every field edge against
  measured schema plus owner alignment evidence.
- [ ] Hash baseline before and after the transaction. Derive registration and coverage only from
  admitted overlay/CAS artifacts, never an inline owner payload.
- [ ] Focused tests + Ruff. Commit: `feat: admit acquisition epochs through passports`.

## Workstream 4 — Attach the overlay to every existing L1 read

- [ ] RED integration tests prove `l1_dcat_variable_availability` and the generation-cycle value
  profile both see admitted epoch rows and ignore quarantine. A marker-only attachment is
  insufficient.
- [ ] Add one Data Forge read-session factory that attaches baseline and overlay read-only and
  exposes union views with legacy table schemas plus audit views for epoch/provenance.
- [ ] Route `DatasetCatalogStore`, data-state availability, and the generation-cycle direct reader
  through that chokepoint. Do not add a sibling availability adapter.
- [ ] Prove baseline bytes are identical before/after and removing the real union turns RED.
- [ ] Focused tests + Ruff. Commit: `feat: expose acquisition epochs through L1 catalog reads`.

## Workstream 5 — Execute the local-lift demonstration

- [ ] Add the measured data registry edge from the existing corrected-firm-panel field
  `corrected_exit_bias` to `cells.distress_score`, unit `ratio`, with exact source/dataset/schema and
  L5 authority refs. Code remains generic over all registered edges.
- [ ] RED tests reject cross-dataset edges, missing fields, out-of-range ratios, field-name-only
  self-attestation, incomplete source rows, and hardcoded target branches.
- [ ] Execute one local source query over the full 11,574-row denominator, measure schema and range,
  derive the passport, and append canonical aggregate observation rows at epoch 1.
- [ ] Recompute N13a-style demand supply before/after and call the actual L1 availability consumer.
  Re-run the demanding L6/world-slot availability stage. Record closure or a typed deeper state.
- [ ] Execute rank-1 `avg_hh_income_uah` as a separate no-write attempt and require the honest
  `basis_mismatch` terminal.
- [ ] Focused tests + Ruff. Commit: `feat: execute local acquisition world growth`.

## Workstream 6 — Execute one bounded live-fetch lane

- [ ] RED tests prove missing N13a authorization, second variable/call, unsafe license, absent
  profile, no raw journal, fabricated response, metadata-only conformance, and orchestration bypass
  all fail closed.
- [ ] Resolve one World Bank CPI/deflator plan from the real catalog; narrow the request to Ukraine
  and a declared period through request-side filters only. Run the N13a harness/simulator gate before
  spending the call.
- [ ] Execute via `run_orchestrated_ingestion` into a dedicated CAS, produce a `DataSnapshot`,
  measure the first fetched sample under quarantine, then validate the complete passport. Admit only
  if the measured `country_code/year/value` structure, unit/basis, license, PII, checksum, watermark,
  and L5 cap all pass.
- [ ] Record call count, bytes, wall time, heartbeats, CAS/snapshot refs, quarantine census, and
  before/after baseline hash. Never claim this already-supported metric closes a D2 residual or a
  capstone route.
- [ ] Focused tests + Ruff. Commit: `feat: execute bounded live catalog acquisition`.

## Workstream 7 — Derived provenance and real-terms acceptance

- [ ] RED tests: derived-as-observed; nominal requested as real without transform; missing deflator
  or base year; basis mismatch; authority inflation; recipe identity mutation; second method
  recomputation instead of cache reuse.
- [ ] Extend the existing operation/CAS pattern with a strict derivation certificate. Recipe identity
  binds input hashes, method/version, parameters, auxiliary deflator hash, deflator version, base
  year, unit transform, and assumptions.
- [ ] Produce one nominal monetary input acceptance case only if its basis authority is sufficient;
  otherwise retain the measured `basis_mismatch` refusal. Use the admitted connector-acquired CPI
  as auxiliary input when available.
- [ ] Have two distinct declared method lanes request the exact same certified recipe. The first
  writes one derived CAS artifact; the second proves one `FileSystemCAS.has` cache hit and consumes
  the same artifact ID. Derived authority is capped by the weakest input.
- [ ] Focused tests + Ruff. Commit: `feat: certify cached derived observations`.

## Workstream 8 — Lifecycle, frozen receipt, and decisive flips

- [ ] Derive acquisition snapshot registrations from passport/overlay/snapshot manifests and persist
  the acquisition receipt with all `InputRef`s. Close
  `owner_registration_derivation_missing` and `journal_raw_evidence_persistence_missing`.
- [ ] Build the frozen contract from narrow N13a route projections, catalog identity, source
  identities, journal, passport, overlay epoch, availability delta, rerun result, quarantine census,
  and derivation receipt. Keep operational timestamps outside semantic hashes.
- [ ] Implement `--check`, `--write`, `--rederive`, corrupt-field drift, and source flips. Prove
  byte-stability twice.
- [ ] Required behavioral flips: baseline fence removed; passport bypass; quarantine promoted;
  derived as observed; epoch stamp removed; capstone-route laundering; forged registration; raw
  journal removed; field edge hardcoded or detached; recipe order/identity corrupted.
- [ ] Register every output in `architecture/generated_artifacts.toml`; require the import census to
  become 39/39.
- [ ] Focused tests + Ruff. Commit: `feat: freeze acquisition executor contract`.

## Workstream 9 — Targeted closeout and independent review

- [ ] Reopen the failure register and record the post-implementation pattern/capability pass.
- [ ] Run all new focused suites and flips strictly serially.
- [ ] Run Ruff on changed Python files and architecture guardrails.
- [ ] Run cheap `--check` for every consumed frozen artifact (L6, N4, N8, N10a, composition, N10,
  N13a, value gate) and prove their semantic bytes did not move.
- [ ] Run the 39-validator import census, `git diff --check`, protected-path/production-data diff,
  baseline before/after hash proof, and scoped commit audit.
- [ ] Request independent spec-compliance and code-quality review; address only evidence-backed
  findings and rerun their blast radius.
- [ ] Update the GY Rev 18 status and execution ledger with measured results. Commit:
  `docs: close GY-N13b acquisition executor ledger`.

## Acceptance report

Lead with the world-growth event for Phase 6/DS15 readers: selected requirement, evidence chain,
before/after L1 counts, epoch, passport, demanding-stage rerun, and any deeper terminal. Then report
the rank-1 basis refusal, live lane and economics, quarantine census, derivation/caching case, route
preservation, artifact/validator hashes, flips, upstream checks, 39/39 import census, guardrails, and
scoped commits. A typed no-admission outcome is better than a fabricated success; no gap or liveness
denominator may shrink.
