# GY-N13a Acquisition-Layer Reality Census Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` and execute one mutating task at a time.
> Every task follows RED -> observed RED -> minimal GREEN -> focused regression -> scoped commit.

**Goal:** Turn the GY-N10 acquisition terminals into a complete, executable, recurring map of
catalog resolution, route reality, plan-generation readiness, connector liveness, and ranked data
growth without changing engine behavior or admitting probe data.

**Canonical design:** GY plan Rev 17,
`docs/plans/active/layer3-slices/GY-engine-subordination.md`, especially GY-N13a and
sections 3.5.6, 3.5.7, 3.5.9, 3.5.10, 3.5.11, and 3.5.12. This plan sequences that already-approved
design; it does not create a competing architecture.

**Architecture:** A validation-owned, read-only census builder opens the production DuckDB catalog,
delegates FetchPlan creation to the existing `DatasetCatalogGraph` and `RetrievalService`, and
recomputes every status from catalog rows, upstream narrow projections, or journaled probe evidence.
A separate explicit live-capture mode performs bounded shadow characterization into a quarantine
journal. It never invokes a FetchPlan executor, ingestion orchestrator, canonical store writer, or
world/CG owner. The committed census content-binds the catalog, the three narrow N10 route
projections, the data-enumerated connector-family table, and its journal; run timestamps and wall
time stay outside content hashes.

**Tech stack:** Python 3.14, DuckDB, existing PolicyOS catalog/retrieval/connector owners, Pydantic v2
strict DTOs where an artifact crosses a boundary, stdlib JSON/hash/fsync, pytest, Ruff, generated
JSON artifacts.

**Status (2026-07-16):** `in_progress`

## Landing and isolation receipt

- N10 merge-tree: clean tree `52f11199010702c619fa22d71d0e06e297e943cf`.
- N10 merge commit on main: `7e035a42695add42540c260bf61e6110d0fa3c93`.
- Audited capstone: commit `6fcbd2c11b817745d266a73be247d7d59ebad04c`, contract
  `sha256:fb1194882178801f0d08835e7c6683433ace055bcbd3ea44e6ecd6ba99a742a6`.
- Post-merge serial smoke: capstone, N4, N8, N10a, composition, and architecture guardrails passed.
- Lane: `.worktrees/gy-n13a` on `codex/gy-n13a-acquisition-census`; `.worktrees/gy-n10` retained.
- Atlas isolation: never touch `.worktrees/atlas-ds0`, `docs/brand/**`, `apps/**`, or
  `docs/plans/active/atlas-slices/**`.

## Global constraints and stop law

- Production data is read-only. The canonical source is
  `production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb`; the tool takes an
  explicit `--catalog-path` because the ignored production snapshot is intentionally absent from the
  worktree.
- Full denominators are owner-derived: all distinct `metric_id` values, all cycle-relevant demand
  variables, all three actual capstone routes, and all distinct `connector_id` values. No expected
  count or family name is implementation input.
- Owner validation is fail-closed. Presence, shape, strings, or self-attestation never count as
  executable/schema/liveness evidence.
- No CG/world engine import, execution, or mutation. No FetchPlan execution. No canonical data-store
  write. Probe response bytes are quarantine-only evidence.
- Every live attempt is journal-first, one request variable at a time, with typed byte/time/rate/call
  budgets, heartbeat records, and bounded reads through the existing HTTP limits.
- Characterization precedes classification. There is no response repair. `dead` is earned only after
  the family-specific honest levers represented by sampled catalog requests have been tested.
- Dead endpoints, schema drift, auth, rate limits, and license uncertainty are findings, not task
  failures. Stop only for class-level catalog corruption, an unavoidable unsafe license/ToS probe,
  or required engine behavior change.
- `--check` and `--write` are offline. Network access occurs only behind an explicit live-capture
  flag. `--write` is byte-stable twice.
- Run targeted tests only; never full pytest/backend verify/CI parity.

## Pattern pass

- Relevant failure patterns: P01/P02/P03 (capability reality), P04/P05/P09/P15 (status and
  authority), P07/P08 (replay/time), P10/P14 (semantic/evidence truth), P29/P31/P32/P33/P34
  (behavioral proof, class-level invariants, trust-by-form, probe teaching, honest exclusion).
- Existing risks found: Task-0 catalog/family audits pin snapshot conclusions; schema profiles are
  metadata-only; connector scorecards can report `watch` while operational signals remain unknown;
  N10 prose contains a stale water-quality hypothesis that is not the actual frozen unseen route.
- Smallest correct pattern: one generic catalog reader, one derived classification algebra, one
  journal-first quarantine boundary, one data-enumerated family denominator, and one behavioral
  no-execution fence.
- Capability labels before work: `bridge_missing`, `artifact_missing`, `verification_missing`,
  `surface_missing`, `semantic_test_missing`. Closure signal is a registered generated artifact plus
  journal, recurring command, focused negative/e2e tests, and decisive source flips.

## File and ownership map

### New files

- `tools/quality/validation/layer3_gy_n13a_acquisition_census.py`: strict DTOs, catalog queries,
  projection hashing, resolution/route/backlog derivation, FetchPlan proof projection, liveness
  recomputation, and canonical hashing.
- `tools/quality/validation/check_layer3_gy_n13a_acquisition_census.py`: CLI, offline
  check/write/corrupt/source-flip lanes, explicit live capture, no-execution guard, and report output.
- `tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py`: focused owner, artifact,
  fence, flip, and byte-stability tests.
- `architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json`: frozen census.
- `architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json`: bounded raw-response
  quarantine journal and attempt economics; no canonical observations.
- `docs/superpowers/journals/2026-07-16-gy-n13a-acquisition-census.md`: measured execution ledger.

### Existing owners consumed without engine changes

- `src/polisyos/data_forge/domains/catalog/knowledge/search.py` (`DatasetCatalogGraph`).
- `src/polisyos/data_forge/domains/catalog/knowledge/store.py` (catalog binding owner).
- `src/polisyos/fabric/retrieval/service.py` (`RetrievalService._resolve_via_catalog`).
- `src/polisyos/fabric/connectors/http_limits.py` (bounded response/body rules).
- `src/polisyos/fabric/connectors/testing/simulator.py` and `harness.py` (pre-live family gauntlet).
- N10 capstone, N4, N8, N10a, composition artifacts, L6 substrate artifact, and value-gate artifact,
  each consumed through a declared narrow projection.

## Task 1 — Freeze the schema, denominator owner, and hash boundary

**Files:** create both Python modules and the focused test file; create the execution journal header.

- [x] Define strict DTOs for catalog identity, metric resolution, reverse demand residual, route
  evidence, FetchPlan projection, probe request/profile/budget/raw response, derived liveness,
  family scorecard, backlog row, projection binding, and census manifest.
- [x] Write Task-1 RED tests for strict DTO invariants, data-derived metric/family denominators,
  malformed-owner-row and fake-profile failure, exact/alignment/unresolved evidence shape, and
  byte-stable semantic hashing with top-level-only run-economics exclusions.
- [x] Run the focused file and record the expected import/contract failures in the journal.
- [x] Implement only the schema, deterministic JSON/hash utilities, and catalog identity/query owner
  needed to make schema tests GREEN.
- [x] Commit: `feat: define N13a census evidence schema`.

Task 1 does not claim route classification, real FetchPlan generation, an execution fence, live
journal ordering, or connector characterization. Those behavioral witnesses are owned explicitly by
Tasks 2–5 and remain RED/GREEN work there.

## Task 2 — W1 full catalog-to-runtime seam and reverse denominator

**Files:** extend builder/checker/tests/journal.

- [x] Query every distinct binding metric. Resolve `exact` only when the metric is cycle-visible in
  the runtime canonical-variable read path; otherwise derive alignment candidates from owner rows,
  preserving confidence, proxy status/penalty, method, and ambiguity; otherwise `unresolved`.
- [x] Never choose a semantically arbitrary alignment silently. Persist the deterministic best
  candidate plus the complete candidate set and an ambiguity indicator; validation recomputes all of
  them from DuckDB.
- [x] Derive the reverse denominator generically from declared JSON paths over the actual capstone
  outcome/objective/lever targets, L6 knob targets, and value-gate requirements. Classify missing
  executable support as typed `binding_gap` or `connector_gap` with local evidence counts.
- [x] Add negative tests for dropped metric, pinned status, modified confidence/proxy penalty,
  denominator shrink, fake binding, and a newly inserted catalog family/metric fixture.
- [x] Record measured counts and exact residuals in the execution journal.
- [x] Commit: `feat: census acquisition metric resolution`.

## Task 3 — W2 evidence-derived classification of the three N10 routes

**Files:** extend builder/checker/tests/artifact projection/journal.

- [ ] Extract the three routes from the frozen capstone by role; do not encode education,
  first-vertical, unseen, water quality, or expected class as classifier inputs.
- [ ] For each route, measure local observations/L4 or pack evidence, binding counts by execution
  tier, alignment evidence, N7 gap/strategy kind, method/estimand blocker evidence, and exact missing
  link.
- [ ] Derive `local_lift`, `live_fetchable`, or `not_a_data_gap` by an explicit precedence algebra.
  Persist both evidence and derived label. Validate by recomputation from the narrow route projection
  and catalog—not by comparing pinned labels.
- [ ] Add RED/GREEN mutations for label pinning, route evidence removal, local-row count change,
  executable-tier change, and stale expected-route prose. Make the actual unseen capstone route the
  denominator even if it disproves the reconnaissance hypothesis.
- [ ] Commit: `feat: classify N10 acquisition routes from evidence`.

## Task 4 — W3 real FetchPlan generation with a hard execution fence

**Files:** extend builder/checker/tests/journal only; do not edit retrieval/connector execution code.

- [ ] Open the real catalog through `DatasetCatalogGraph` and inject it into
  `RetrievalService._resolve_via_catalog` for a declared data-derived sample including every W2
  metric with an executable binding plus representative remaining tiers/families.
- [ ] Persist narrow FetchPlan proofs: metric, connector ID, request dataset ID, profile ID, filters,
  selected distribution, and owner type. Validate every field against owner output/catalog rows.
- [ ] Install a behavioral execution fence around proof generation. Forbidden owners include
  `FetchExecutor.execute/preview`, `run_orchestrated_ingestion`, connector `fetch`, and canonical
  persistence. A call raises a typed N13a violation before side effects.
- [ ] Add the decisive source flip that removes/bypasses the fence while markers remain; it must turn
  RED. Add a plan-generation e2e test proving owner FetchPlans exist without world growth or
  acquisition execution.
- [ ] Commit: `feat: prove catalog FetchPlan generation without execution`.

## Task 5 — W4 stratified live connector characterization

**Files:** extend builder/checker/tests; create journal artifact; update execution journal.

- [ ] Enumerate connector families only from `SELECT DISTINCT connector_id`. Resolve concrete
  connector classes through the live registry and run the simulator/harness gauntlet before any live
  request; record typed dry-run evidence per family.
- [ ] Select 10–15 rows per family with a declared deterministic stratification over execution tier
  and quality bucket, preferring explicit open-license/no-auth candidates within each stratum without
  hiding excluded unsafe rows.
- [ ] Carry the exact schema-profile projection and derived HTTP budgets/rate limits in every request.
  If the owner profile cannot substantiate a schema contract, derive
  `alive_schema_unverified`, never `alive_conformant`.
- [ ] For every attempted network call: append+fsync the request/response envelope before any
  classifier consumes it; issue one bounded request; never repair the response; record heartbeats,
  call count, wall time, bytes, status, headers needed for diagnosis, bounded body/checksum, and
  safety/license outcome. Nothing enters a canonical store.
- [ ] Recompute liveness (`alive_conformant`, `alive_schema_drift`,
  `alive_schema_unverified`, `dead`, `auth_required`, `rate_limited`, `license_unclear`, and typed
  bounded-transport failures) from journal + profile evidence. Derive per-family scorecards and
  D3 execution-tier decay findings.
- [ ] Add focused fake-owner tests and decisive flips: dead->alive relabel; live scorecard row with no
  raw journal; hardcoded family denominator; schema self-attestation; reordered/unearned family
  result. All restore source/artifacts in `finally` and prove the clean checker after restoration.
- [ ] Run one safe family-at-a-time live capture with declared budgets and record economics. Commit:
  `feat: journal N13a connector liveness census`.

## Task 6 — D2 growth backlog, artifact lifecycle, and recurring lane

**Files:** extend builder/checker/tests; create frozen census; modify generated-artifact registry,
GY plan status, and execution journal.

- [ ] Rank every W1 reverse residual. Use the existing N7/VOI owner only where its contract accepts
  the metric-level input. Otherwise label the score `interim_binding_demand_rank`, compute the
  declared binding-confidence x route-demand ordering, and persist
  `voi_owner_integration = "routed_to_gy_n13b"`; never call it VOI.
- [ ] Bind narrow identities: DuckDB content SHA, capstone route projection SHA, connector-family
  table SHA, upstream demand projection SHA, and journal content SHA. Keep observed-at/wall-time
  economics outside the semantic content hash.
- [ ] Implement `--check`, offline `--write`, explicit `--capture-live`,
  `--corrupt-field-drift-check`, and `--source-flip-mutations`. The recurring command performs
  dry-run -> bounded live journal -> offline census write/check and creates a dated run identifier
  outside the schema/content hash.
- [ ] Register both outputs in `architecture/generated_artifacts.toml` with generator, checker,
  freshness, commit policy, and stale-output failure.
- [ ] Prove `--write` twice byte-identical. Add nested decisive corruptions and backlog-order flip.
- [ ] Update the GY plan/ledger with measured status, typed findings, N13b lane decision inputs, and
  remaining capability labels. Commit: `feat: freeze recurring N13a acquisition census`.

## Task 7 — Targeted closeout and independent review

- [ ] Reopen the failure/repair register and record the closeout pattern pass.
- [ ] Run the new focused tests and every decisive flip serially.
- [ ] Run Ruff over changed Python files.
- [ ] Run `--check` for N13a and every consumed frozen artifact: N10 capstone, N4, N8, N10a,
  composition, L6, and value gate. Confirm their bytes did not change.
- [ ] Run the validator import census and require 38/38.
- [ ] Run architecture guardrails.
- [ ] Inspect `git diff --check`, protected-path diff, production-data diff, worktree status, and
  scoped commit history.
- [ ] Request independent spec-compliance and code-quality review; fix only evidence-backed findings
  and rerun affected checks.
- [ ] Commit closeout evidence if needed: `docs: close GY-N13a census ledger`.

## Acceptance report

The final report must lead with the measured N13b decision inputs and include: resolution counts,
full per-family liveness table, the three actual route classifications and exact missing links,
top-10 backlog with demand sources, artifact/validator SHA-256, all flip outcomes, live calls and wall
time per family, upstream unchanged checks, 38/38 import census, architecture result, merge and lane
commits, and any honestly typed residuals. No liveness inflation and no denominator shrink are
permitted.
