---
plan_id: layer3-gx-universal-free-growth-runtime-hardening
title: "GX - Universal Free-Growth Runtime Hardening"
type: slice-plan
status: "active - closeout blocked"
created: 2026-06-12
slice: GX
scope: cross-slice
depends_on:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/reference/policy-design-case-failure-patterns.md
  - docs/plans/active/layer3-slices/G0-capability-data-inventory-triage-discipline-freeze.md
  - docs/plans/active/layer3-slices/G1-data-grounding-existing-assets-acquisition.md
  - docs/plans/active/layer3-slices/G2-causal-forecast-search-engine.md
  - docs/plans/active/layer3-slices/G3-analytics-search-engine.md
  - docs/plans/active/layer3-slices/GL-legal-mandate-search-engine.md
  - docs/plans/active/layer3-slices/G4-shadow-to-governed-promotion-gate.md
  - docs/plans/active/layer3-slices/G5-first-proving-ground-conversion.md
  - docs/plans/active/layer3-slices/G6-bounded-agent-arbitrary-request-grounded-result-or-abstention.md
  - docs/plans/active/layer3-slices/G7-envelope-widening-one-case-to-region.md
  - docs/plans/active/layer3-slices/G8-health-metric-governance-and-corpus-rebasing.md
floor_id: layer3_grounding_subordination
metric: layer3_universal_free_growth_runtime_hardening
source_roadmap: docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
---

# GX - Universal Free-Growth Runtime Hardening

## For Agentic Workers

This is a strict repair plan, not a design note and not an optional cleanup.
The objective is to stop Layer 3 from passing by authored summaries, stale
references, case-specific literals, or legacy fallback paths. The repaired
runtime must grow from new data and governed artifacts, not from code changes
that enumerate domains.

The operating rule is:

```text
new data changes the search frontier
new governed artifact changes admission
new reducer input changes closure
runtime code does not change for a new domain case
```

Do not build a new wrapper while keeping the old fallback. Do not mark the old
path deprecated but reachable. Do not allow a validator to pass because a field
exists. If a replacement producer, resolver, or reducer is not wired, the
outcome is a typed blocker or fail-closed readiness, not a positive status.

## Non-Negotiable Kill Rule

Runtime and core contract modules must not contain domain literals that influence
closure, admission, promotion, calibration, or conversion. This applies to
`src/polisyos/runtime/**/*.py`, `src/polisyos/core/**/*.py`, especially
`runtime/quality` and `core/contracts`, and to any builder or validator reachable
from Layer 3.

Forbidden runtime literals and patterns:

- Construct ids used as logic: `firm_survival`, `credit_access`,
  `credit_program_enrollment`.
- Case ids used as logic, defaults, branch keys, or builder-generated inputs.
- Scenario-family mappings or re-exports used for closure/admission.
- Placeholder refs, manifest-only promoted refs, and synthetic `cas://...`
  records used as authority-bearing inputs.
- Placeholder digests such as `sha256:111...` or any repeated-character digest
  used outside a negative fixture.
- Manually authored positive outcomes such as `grounded_or_uncertain`,
  `calibrated`, and `governed_promoted` in builders, default objects, summaries,
  manifests, or handoff records.

Positive outcome strings may exist only in centralized reducer truth tables,
DTO type declarations, generated artifacts, and negative/positive tests that
prove the reducer behavior. They may not appear in ad hoc bundle summaries,
default requests, default rows, fallback branches, or readiness writers.

Required first command before any implementation:

```bash
cd policy-engine
rg -n 'firm_survival|credit_access|credit_program_enrollment|ua-msme-affordable-loans-2022|KNOWN_CONSTRUCTS|REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS|sha256:|grounded_or_uncertain|calibrated|governed_promoted' src/polisyos/runtime src/polisyos/core tools/quality/validation tests/unit/runtime tests/repo_quality
```

The implementation must drive all runtime/core hits outside approved
reducer/type modules and tests to zero. If a hit remains because it is a
legitimate enum or test fixture, add it to a narrow, audited allowlist consumed by
the lint tool. An allowlist entry must name the owner, reason, removal condition,
and approved human sign-off record.

## Pattern Pass

This repair targets recurring failures in the failure/repair register:

| Pattern | Current failure mode | Required closure move |
| --- | --- | --- |
| P01 | Capability appears implemented because contracts and artifacts exist. | Prove producer -> persisted artifact -> bridge -> consumer -> negative/e2e test. |
| P02 | Search, admission, and closure coexist but do not bind. | Add explicit bridges and dereferenced refs between every stage. |
| P03 | Internal facts are hidden behind optimistic summaries. | Expose reducer inputs, rejected candidates, and missing refs on audit surfaces. |
| P04 | Local statuses flatten into green readiness. | Centralize reducers and mixed-outcome truth tables. |
| P05 | Search hits or projections leak into authority. | Enforce `authoritative_for` and `may_not_use_for` at consumers, not only producers. |
| P07 | Replay refs are present but not sufficient to reproduce decisions. | Persist query plans, index versions, reducer input hashes, and rule versions. |
| P10 | Validators pass shape, not semantic adequacy. | Add mutation tests and contradiction fixtures that must fail. |
| P12 | Producers do not handshake before promotion/conversion. | Use concept/scope/admission records before governed artifacts are emitted. |
| P14 | Evidence rows inflate independence through repeated wrappers. | Dereference and collapse lineage before counting evidence. |
| P15 | Candidate or synthetic outputs become authority through routing. | Keep synthetic/candidate records blocked until producer evidence validates them. |
| P25 | Search frontier is projected as exhaustive or authoritative. | Persist search incompleteness and keep frontier support separate from producer evidence. |

## Target Architecture

Layer 3 must use the same hard pipeline everywhere:

```text
SearchRequest
-> SearchLedger/SearchCandidate
-> AdmissionResult
-> MaterializedGovernedArtifact
-> ResolvedRef
-> ClosureReducer
-> ReadinessManifest
-> Consumer/Audit/Public surface
```

No stage may skip the previous stage. A search hit is not a binding. A binding
ref is not a dereferenced artifact. A dereferenced artifact is not closure. A
closure is not useful-design credit unless the G5 reducer says so.

## Asset Registry — Do Not Rebuild

A June 2026 sweep of `src/polisyos` found that the capabilities GX hardens
**already exist** as engine-side assets; the prior Layer-3 failure was not
missing capability but runtime code that reimplemented or bypassed it (the G1
hollow search next to a live catalog engine is the canonical example). The
following assets are load-bearing. A GX task that builds, re-derives, or stubs
any of them is mis-specified: subordinate the asset through the waist instead.

| Capability | Lives at | GX/GY role |
| --- | --- | --- |
| Policy design DAG | `scientist/orchestration/workflows/policy_design.py` (`run_policy_design_workflow`) | the design producer subordinated in GY |
| Data search engine | `data_forge/domains/catalog/knowledge/search.py` (`DatasetCatalogGraph.search_datasets`, hnsw+text) | the canonical search engine Task 2 adapts |
| Evidence contracts | `ir/analytics/` (93 files: `partial_identification`, `estimand`, `transportability`, `forecasting_uncertainty`, `welfare`, `dual_certificate`, `data_fusion`, …) | the reducer/port vocabulary — reuse, do not re-declare in `runtime/quality` |
| Legal→design knobs | `lex/interventions.py` (`TemporalInterventionSequencer`, `HierarchicalPolicySearchAdapter`, `CompiledLexIntervention`) | the design-space algebra subordinated in GY |
| ID/bounds/transport/DRO | `foundry/methods/catalog/causal`, `optimization/moment_dro` | computation behind G2/G3 |
| Literature pipeline | `scholar/search` (provider failover, CAS-first) | L2 growth path (GY) |

**No pass for the smart component.** Subordinating a sophisticated engine does
not exempt its output from GX rails. A `scientist_policy_design` bundle is a
`derivation` over corpora; it carries authority only if its producer-root chain
(Producer Root Chain Rule) reaches `measurement` roots (L4 panels, SKG). The
DAG's internal gates (judge stack, candidate funnel, normative arbitration) are
engine-local checks, never waist authority. The constitution forbids a second,
weaker governance path for "the smart component" (§3); subordinated outputs flow
through the same resolver, reducer, and producer-root validation as everything
else.

## Outcome Goal

GX is not complete when all bad patterns are forbidden. GX is complete only when
the hardened pipeline produces the first measured, reducer-authored outcome for
the pinned flow on canonical corpora.

Required final outcome:

```text
pinned case request
-> canonical corpus search ledgers
-> measured recall/freshness
-> dereferenced admission/materialization refs
-> G4/G5 reducer inputs
-> reducer-produced outcome
```

The outcome is not predetermined. Acceptable final reducer-produced outcomes are:

- `grounded_abstention`, if measured search and demand-pull prerequisites prove
  there is no admissible grounding path but the abstention itself is grounded.
- `grounded_limited`, if the reducers unexpectedly produce a real grounded
  limited outcome from measured inputs and dereferenced governed artifacts.
- `search_ceiling_repair_required`, if no-hit/blocked status cannot distinguish a
  real domain limit from insufficient search recall/freshness.
- a typed blocker, if a specific required producer, resolver, corpus, demand, or
  materialization input is missing.

Not acceptable:

- completing GX with all statuses `blocked` or `not_measured` without running the
  pinned flow through the hardened reducers;
- forcing a conversion to useful-design credit;
- accepting a readiness pass that was not recomputed from measured inputs.

## As-Built Status (2026-06-13, derived from artifacts, not prose)

The minimal shippable set is **executed**. This is machine-confirmed, not
asserted: `layer3_gx_expected_red_checks.json` carries
`provisional_task12_complete: true`, and the GX validator
(`check_policy_design_case_layer3_gx_hardening.py`) runs. Read this table before
touching any task — do not redo finished work.

| Task | State | As-built evidence |
| --- | --- | --- |
| Task -1 baseline | done* | `layer3_gx_baseline_note.json` (*see worktree caveat below) |
| Task 0A data home | done | `layer3_gx_pinned_request.json`, `..._scope_seed_rows.json`, `..._concept_alias_seed_rows.json`, `..._demand_pull_request.json`; `layer3_gx_data_home.py` |
| Task 0 validator/guards | done | `check_policy_design_case_layer3_gx_hardening.py`; `..._runtime_literal_lint.json`, `..._producer_registry.json`, `..._producer_root_chain_report.json`, `..._reducer_integrity_report.json`, `..._positive_status_provenance.json`, `..._status_vocabulary_delta.json`, `..._independent_audit_sample.json`, `..._human_approval_receipts.json` |
| Task 5 resolver | done | `required_reference_resolver.py` (`resolve_required_ref`, producer_type/root, sha256 guards) |
| Task 4 reducers | done | `layer3_status_reducers.py` (all 8: `reduce_g1..g8` + gl, with provenance) |
| Task 2 (minimal, G1) | done | `g1_search_measurement_status=pass` in the vertical report; `layer3_gx_concept_alias_graph.json` |
| Vertical G1→G4→G5 | done | `layer3_gx_vertical_pinned_route_report.json` |
| Provisional Task 12 | done | `layer3_gx_provisional_pinned_route_outcome_report.json`: outcome `typed_blocker` via `reduce_g5_conversion_outcome`; `..._provisional_blocker_audit_record.json` |

**The pinned-route outcome is an honest blocker** (g1 grounding closure
`typed_blocker`, g4 `promotion_blocked`, g5 `unchanged_blocker`), reducer-produced
and measurement-rooted. This is the GX win — measured absence, not authored lie —
and the baseline GY moves from.

**Rollout is NOT done.** The validator is **red by design**: ~1184
`reducer_provenance_missing` issues on legacy `g2/g3/gl/g6/g7/g8` artifacts that
were never hardened. These are catalogued in `layer3_gx_expected_red_checks.json`
(status `active_post_provisional_task12`) — expected red, not drift. Driving that
count to zero (real provenance) or to honest demotion is the **rollout progress
meter**: GX Tasks 1/6/7/9/11 plus all of GY exist to close it. The plan is
complete only when expected-red is empty or every remaining entry is an
intentional, catalogued blocker.

**Worktree caveat.** The branch shows worktree-merge commits (`fold g1 search
worktree`, `fold binding waist worktree`, `fold honest grounding worktree`,
`consolidate pending changes`). GX was executed across parallel worktrees and
consolidated, so Task -1's "clean baseline → first GX red attributable to a GX
fixture" guarantee was bypassed in practice. Before trusting the done-state,
confirm on the consolidated branch that the validator's red set equals the
`expected_red_checks` catalogue (no uncatalogued drift).

## Scope Budget And Stop Rules

GX is intentionally vertical-first. The minimal shippable set is:

```text
Task -1 -> Task 0A -> Task 0 -> Task 5 -> Task 4 ->
minimal Task 2 for G1 -> vertical G1/G4/G5 route -> provisional Task 12
```

Everything beyond that is a follow-on slice unless the provisional pinned route
proves the mechanism works. If the minimal shippable set exceeds the agreed
engineering budget or cannot produce a provisional reducer outcome, stop and
revise the plan instead of widening the scope.

Task size rules:

- Task -1, 0A, and the provisional pinned-route run are small tasks: one isolated
  PR or commit each.
- Task 0, 4, and 5 are medium tasks and must be split if they touch more than one
  major runtime module plus tests.
- Task 2, 6, 7, 8, 9, 10, and 11 are rollout tasks. They may not begin until the
  minimal shippable set has a recorded outcome.
- Any task that grows by more than 50 percent over its initial estimate triggers a
  stop-and-review note before more code is added.

## Validation Authority Boundary

During minimal ship, old per-slice readiness validators and GX validators will
disagree. That disagreement must be explicit, not flattened into green readiness.

Required boundary artifact:

- `architecture/policy_design_case/layer3_gx_validation_authority_boundary.json`

For every Layer 3 slice, record:

```text
slice_id
gx_migration_state
old_validator_status
gx_validator_status
readiness_authority
may_count_for_gx_closeout
superseded_by
issue_codes
```

Allowed `gx_migration_state` values:

- `gx_hardened`
- `legacy_validator_superseded`
- `legacy_validator_no_gx_authority`
- `blocked_by_gx_migration`

Until a slice is `gx_hardened`, its old green readiness status may remain useful
for legacy diagnostics but has no GX closeout authority. A public/readiness
surface must not present legacy green and GX red as equivalent signals.

## Mechanism Over Prohibition

The primary defense is recomputation, not grep. The hardening validator must
recompute reducer decisions from dereferenced persisted inputs and compare those
decisions with persisted Layer 3 artifacts. A positive persisted status is valid
only when it carries:

```text
produced_by.reducer_id
produced_by.reducer_version
produced_by.rule_version
produced_by.input_hashes
produced_by.output_hash
```

Any positive status without reducer provenance is a fail, even when no forbidden
literal is present. Runtime literal lint is secondary. It is a useful tripwire,
not the trust mechanism.

Recompute-and-compare is necessary but not sufficient. It catches hand-edited
artifacts and builder/reducer drift; it does not prove that reducer inputs were
real. Therefore every positive status must also pass producer-root validation.

## Producer Root Chain Rule

Every authority-bearing artifact must carry a typed producer record. Producer
types are:

| Producer type | Meaning | Can be root for positive status? |
| --- | --- | --- |
| `measurement` | Reads a corpus, index, external source, tool-loop trace, or materialized store and emits observations with snapshot/hash evidence. | Yes |
| `external_request` | Human/API/request-side demand, scope, or policy question input. | Yes, only for demand-side facts |
| `derivation` | Pure transformation over other artifacts. | No, unless its provenance chain reaches valid roots |
| `test_fixture` | Test-only data under explicit fixture paths. | No production authority |

The validator must walk producer chains to their roots. A positive production
status is valid only if every supply-side fact terminates in at least one
`measurement` root and every demand-side fact terminates in an `external_request`
or measurement root. A chain that terminates in `derivation`, an untyped
producer, or a production `test_fixture` fails even when artifacts are persisted,
hash-addressable, and recompute-clean.

This explicitly forbids the cheap bypass where a synthetic method candidate is
dumped to JSON with `producer_ref`, content hash, and clean reducer provenance.
Persisted fake is still fake unless the producer chain reaches measurement or
external-request roots of the right kind.

## Measurement Replay Rule

A producer label is not enough. A `measurement` root must be machine-replayable.
Every measurement artifact must include:

```text
measurement_id
producer_ref
producer_version
corpus_ref
corpus_path
corpus_snapshot_hash
query_or_probe
execution_parameters
expected_output_hash
replay_command
replay_environment
```

The GX validator must automatically re-execute a deterministic subset of
measurement roots on every run and compare the replayed output hash with the
persisted hash. The subset must include all measurement roots on the vertical
pinned route and a deterministic sample for rollout surfaces. Manual audit
remains a second line of defense, not the only proof that a measurement happened.

If a measurement root is not replayable, its descendants are treated as
`not_measured` or typed blockers. Copying a corpus path and snapshot hash into a
JSON record is not measurement.

## Demand/Supply Authorship Boundary

Authored input is legal only on the demand side. Supply-side facts must be
measured.

Demand-side artifacts may be authored when they represent what is being asked:

- pinned request;
- requested scope and audience;
- accountable demand-pull request;
- human/API case request metadata.

Supply-side artifacts may not be authored as facts:

- corpus contains a metric, edge, proof, source contract, calibration, or legal
  threshold;
- a method candidate is valid;
- recall/freshness is adequate;
- an alias resolves to corpus rows;
- a promotion, grounding, calibration, or abstention is supported;
- an admission or materialization artifact is valid.

Admission artifacts are supply-side derivations. They may only be produced by
conformance/admission producers whose own chains terminate in measurement roots,
such as battery runs, resolver checks, calibration evaluations, or corpus
queries. They may not be authored data rows in production.

Concept/alias rows are boundary artifacts. They may be authored as proposed query
expansion hints, but they are `unverified` until a measurement producer resolves
them against corpus rows. Unverified aliases may broaden search; they may not
support positive recall, admission, or closure.

## Human Approval Principal

Any exception requiring human judgment must name the principal and the channel.
For this plan, the approving principal is `deniskopylov` unless a later
repo-owned governance file explicitly replaces that principal.

Valid approval channels:

- PR review sign-off by the required principal and handle.
- A committed approval receipt in
  `architecture/policy_design_case/layer3_gx_human_approval_receipts.json`
  containing principal, handle, artifact refs, decision, timestamp, and reason,
  with the receipt itself referenced by the PR.

Invalid approval channels:

- a JSON field saying `human_approved: true`;
- an agent-authored comment claiming human approval;
- a TODO, note, or unchecked plan item.

The validator must fail allowlist additions, highest-governance vocabulary
changes, and manual audit closeout records unless the required approval receipt
or PR review sign-off is present.

## Global Input Authenticity Rule

Reducers may accept only persisted, hash-addressable artifacts with producer refs
or explicit test-owned fixture artifacts. Inline construction of reducer inputs in
production build/readiness paths is forbidden. This rule applies to every Layer 3
slice, not only G4/G5.

Concretely forbidden:

- hand-built method candidates, source contracts, promotion records, evidence
  rows, demand-pull refs, rejected branches, selected evidence refs, or readiness
  payloads passed directly into reducers;
- strings that look like refs or hashes but cannot be dereferenced;
- producer-less inputs marked `pass`, `calibrated`, `governed_promoted`,
  `grounded_or_uncertain`, or equivalent positive states.

## Vocabulary Delta

New statuses introduced or normalized by GX must be registered before use. Keep
the status lattice small. Missing provenance, inline input, and correction needs
are issue codes, not readiness/closure statuses.

Required vocabulary artifact:

- `architecture/policy_design_case/layer3_gx_status_vocabulary_delta.json`

Required status entries:

- `not_measured`
- `search_ceiling_repair_required`
- `blocked_legacy_fallback`
- `bounded_surrogate`
- `grounded_abstention_candidate`, only if approved through highest-governance
  vocabulary review

Required issue-code entries:

- `layer3_gx_reducer_provenance_missing`
- `layer3_gx_inline_input_forbidden`
- `layer3_gx_producer_root_invalid`
- `layer3_gx_correction_required`
- `layer3_gx_alias_unverified`

For each status, define owner, allowed producers, allowed consumers, composition
with `grounding_disposition`, `conversion_outcome`, `promotion_state`, readiness
status, and whether it can count toward useful-design credit. If composition is
not defined, the status is not legal. Adding `grounded_abstention_candidate` or
any other lattice point requires ADR/human acceptance; the JSON artifact only
records the approved vocabulary delta and cannot authorize it by itself.

## Blocker-Specific Recall Protocol

Grounded abstention requires blocker-specific search adequacy. Global seed recall
is insufficient. For a no-hit pinned construct, use a canonical-corpus overlay
probe:

1. Record the canonical corpus path and snapshot hash.
2. Create an isolated overlay or copy with a synthetic metric-binding shaped like
   the pinned construct and scope.
3. Run the exact production search route, query expansion, and ledger generation
   against canonical corpus plus overlay.
4. Verify the injected binding is found, ranked, and represented in the ledger.
5. Mark overlay results as recall adequacy evidence only. They cannot materialize
   a source contract, admission artifact, or grounding.

If the overlay seed is not found, the outcome is `search_ceiling_repair_required`.
If the overlay seed is found but the real canonical corpus still has no binding,
the search engine may support a grounded-abstention candidate, subject to
demand-pull, producer-root, and resolver checks.

## Current Code-Grounded Failure Examples

These examples are red baselines and "do not repair this way" fixtures. They are
not historical notes. A compliant implementation must either remove the pattern,
fail it with a validator, or convert it into an explicit negative test that
proves the repaired runtime cannot regress.

Line numbers in examples are orientation aids only. A failure example is closed
only when a named lint rule, named reducer-integrity check, named replay check, or
named test supersedes it. A stale line number is not evidence that the example is
obsolete.

### 1. Better G1 search, still domain-authored runtime

`src/polisyos/runtime/quality/proving_ground/substrate_grounding_search.py` now has a real
search path in `_search_l1_dcat_cached(...)`: it wires `DatasetCatalogStore` and
`DatasetCatalogGraph` and calls search APIs instead of relying only on exact
metric-id resolution. That is real progress.

It is not sufficient. `_default_requests(...)` still authors
`credit_access`, `firm_survival`, and `ua_msme_credit_support` as runtime default
logic around line 1045. `_resolver_query(...)` still injects domain-shaped scope
defaults such as `firm`, `msme`, `UA`, and `production_msme_panel` around line
1112. `_bundle_counts(...)` still exposes pinned bundle/case fields around lines
1607-1610.

Why this fails the universal/free-growth bar:

- New data can improve the search frontier, but a new domain still requires
  runtime code changes if the request and scope come from default literals.
- A better search adapter does not make closure construct-agnostic while
  admission is still shaped by a coded case.
- This is P02/P10/P25: the producer improved, but the closure path can still
  pass by authored defaults and shallow adequacy.

Forbidden repair:

- Replacing the old construct literal with a more correct construct literal.
- Moving the literals into a helper named "default" or "fixture" while that
  helper remains reachable from readiness/build paths.

Required repair:

- Runtime requests must come from persisted request artifacts, API/CLI inputs, or
  test-owned temp fixtures.
- Entity scope, population, geography, modality, source-family aliases, and
  construct aliases must come from data-owned concept/scope rows, not Python
  literals in runtime modules.
- The same runtime code must admit or abstain for a newly inserted construct
  without editing runtime Python.

### 2. Health pass after semantic blocker

`layer3_substrate_grounding.py` still has a health side channel in
`_health_metric_delta(...)`: around lines 1541-1544 it writes
`search_recall_status: pass` and `index_freshness_status: pass` directly.
`_bundle_counts(...)` was improved so `grounding_closure_outcome` is passed in
as a parameter around line 1564, but the health report can still self-attest
green while semantic closure is blocked.

Why this fails:

- A closure fix is not complete if another artifact can continue to say "search
  healthy" without replaying the measured search.
- G8 and downstream health governance can consume this as evidence that no
  missed grounding path exists.
- This is P03/P04/P10: hidden internal richness is projected as a flat pass.

Forbidden repair:

- Adding an issue code while leaving status `pass`.
- Marking the pass "diagnostic only" if G8, G5, readiness manifests, or audit
  answers cite it as evidence.

Required repair:

- Health statuses must be reducer outputs from measured recall/freshness inputs.
- If measurement is missing, the status is `not_measured` or
  `search_ceiling_repair_required`, never `pass`.
- The health artifact must carry the exact query set, seed set, index snapshot,
  and misses used by the reducer.

### 3. G1 source contracts can be empty while summaries still look governed

`_source_contract_records(...)` only emits source-contract bindings when a
search result has a materialized binding. That is the right direction. But the
bundle summary still carries positive-looking governance fields beside empty
bindings: pinned case/bundle fields, health metric ids, and resolver-consumed
counts are assembled in `_bundle_counts(...)` around lines 1607-1634.

Why this fails:

- Empty `grounded_source_contracts.bindings` is the semantic fact that matters.
- Surrounding it with governed-looking counts and pass statuses invites a
  structural pass with no source-contract materialization.
- This is the exact P01/P10 failure: artifact shape exists, semantic adequacy
  does not.

Forbidden repair:

- Counting search hits, selected refs, resolver attempts, or adapter paths as
  grounded source contracts.

Required repair:

- Any summary field that sounds like grounding must be derived from
  dereferenced source-contract bindings only.
- If the binding list is empty, closure can only be `grounded_abstention`,
  `search_ceiling_repair_required`, or a typed blocker, depending on measured
  recall/freshness and acquisition state.

### 4. Coverage still contains domain calibration literals

`build_g1_l1_l5_l6_index_coverage_report(...)` still includes a hardcoded
`capability-index-transition://firm-survival-l5-calibration` ref around line
714.

Why this fails:

- L5/L6 coverage is supposed to report what the index contains, not seed a
  particular domain transition into runtime coverage.
- A single domain calibration ref in a generic coverage artifact creates a
  quiet path for domain-specific authority to re-enter admission.

Forbidden repair:

- Renaming the ref to a generic string while preserving the same coded
  case/construct meaning.

Required repair:

- Coverage refs must be read from the index/catalog itself and validated against
  the materialized snapshot.
- Domain calibration refs may exist in test fixtures or persisted governed data,
  not in runtime coverage builders.

### 5. G4 added a local dereference check, but still judges default requests

`build_g4_grounded_contract_set(...)` now calls `_g4_g1_binding_ref_exists(...)`
around line 1517, and the helper at line 1664 dereferences a `repo://...#binding`
selector into G1 bindings. That is a useful repair because it stops some stale
G1 refs from passing by shape alone.

It is still not the universal resolver. `_default_g4_promoted_request(...)`
still authors a UA/MSME source-only promotion request around lines 3197-3224,
including `case_id`, `candidate_ref`, `claim://ua-msme/...`,
`envelope://ua-msme/...`, and `_default_g4_grounded_g1_row()`.
`build_layer3_g4_bundle(...)` still calls `_default_g4_promoted_request(root)`
and `_default_g4_blocked_request(root)` around lines 4133-4134.

Why this fails:

- A family-specific dereference check is not a cross-slice required-reference
  resolver.
- G4 remains able to promote or block synthetic/default inputs instead of
  judging externally supplied governed requests.
- This is P02/P06/P12: a local bridge was added, but the orchestration path still
  originates in hand-authored defaults.

Forbidden repair:

- Adding more `_g4_g1_*` helpers for each family.
- Keeping `_default_g4_*_request` reachable as a fallback after a real resolver
  exists.

Required repair:

- G4 must accept request artifacts from upstream producers or explicit tests.
- All required refs must be resolved through one typed resolver shared by G4/G5
  and negative-tested for stale refs, wrong fragments, missing bindings, and
  family mismatches.

### 6. G5 has a real reducer, but the readiness path bypasses it

`build_g5_conversion_eligibility_ledger(...)` around line 2604 is the correct
kind of function: it computes conversion eligibility from typed upstream inputs.

`build_layer3_g5_bundle(...)` still hand-authors the persisted readiness outcome.
It builds `useful_join` with `conversion_outcome="unchanged_blocker"` around line
948, constructs `Layer3G5ConversionEligibilityLedger(...)` directly around lines
951-972, suppresses snapshot and eligibility issue codes when the outcome is
`unchanged_blocker` around lines 1049-1063, and emits
`Layer3G5GroundedAbstentionQualityRecord(status="pass")` around lines 1085-1087.

Why this fails:

- The correct reducer existing in the module does not matter if the persisted
  bundle path does not call it.
- Suppressing blockers because the outcome is unchanged converts "known bad" into
  readiness green.
- This is P01/P02/P04/P10: reducer capability exists, but the producer/consumer
  path is not subordinated to it.

Forbidden repair:

- Duplicating reducer logic in the builder.
- Hand-authoring the same outcome the reducer would probably produce.
- Treating `unchanged_blocker` as a pass reason for readiness.

Required repair:

- The persisted G5 bundle must call `build_g5_conversion_eligibility_ledger(...)`
  and persist its exact output.
- Readiness status must fail or be blocked when required upstream issue codes
  exist, even if the conversion outcome is unchanged.
- Grounded abstention quality can pass only when the reducer outcome is
  `typed_blocker -> grounded_abstention` and search/acquisition prerequisites
  were measured.

### 7. G5 evidence rows still synthesize authority-shaped hashes

`_g5_readiness_grounded_evidence_rows(...)` around lines 1103-1137 constructs
evidence rows from G1/G4 references and falls back to strings such as
`sha256:g5-g1` and `sha256:g5-g4` when content hashes are missing.
`_g5_readiness_w12d_payload(...)` then adds many UA/MSME status/pass refs around
lines 1140-1188 and beyond.

Why this fails:

- A missing content hash is not a weak hash; it is a missing artifact or missing
  resolver output.
- Status/pass refs authored in a readiness payload are not upstream evidence.
- This is P07/P14/P15: replay and independence are inflated by authority-shaped
  placeholders.

Forbidden repair:

- Replacing invalid placeholders with syntactically valid fake hashes.
- Counting lineage wrapper refs as independent evidence.

Required repair:

- Missing hashes must block dereference or mark evidence `unresolved`.
- Evidence independence must be computed after dereferencing lineage to source
  artifacts, not by counting wrapper rows.

### 8. G2 fixed the old wrong domain, but kept runtime domain literals

`_default_g2_method_request(...)` now targets
`policy.credit_access -> firm.survival` around lines 5606-5625 instead of the old
fertilizer example. That is a better pinned case.

It is still a runtime default with `case_id`, `source_contract_refs`, cause,
effect, target context, treatment structure, and outcome type authored in code.
`_default_g2_runtime_method_candidate(...)` around lines 5628-5685 still creates
a synthetic method candidate with placeholder `sha256:` refs, pass assumption
gates, and a hand-written uncertainty interval. `_default_g2_recall_seeds(...)`
around lines 5852-5866 still measures recall against fertilizer/food-nutrition
seed rows, which is not the same question as the pinned credit/survival blocker.

Why this fails:

- "Right pinned literals" are still literals.
- Synthetic candidates with pass-shaped diagnostics remain dangerous even when
  downstream gates currently block them.
- Global recall seeds cannot prove recall for the blocker-specific search path.
- This is P10/P15/P25.

Forbidden repair:

- Updating the default request each time the pinned case changes.
- Marking synthetic method candidates `fail_closed` while preserving
  authority-shaped pass fields and placeholder refs in production readiness.

Required repair:

- G2 method requests must come from governed source-contract or case-request
  artifacts.
- Synthetic candidates belong only in negative fixtures and must be impossible to
  consume as readiness evidence.
- Recall/freshness must be reported at two levels: global corpus health and
  request/blocker-specific search adequacy.

### 9. G8 can call search healthy without blocker-specific proof

`build_g8_open_question_answer_ledger(...)` reads G5 outcomes around lines
1680-1703, then answers `8.4-search-recall-freshness` as
`answered_currently_healthy` when `ceiling_gate.status` is not
`search_ceiling_repair_required` around lines 1787-1803. The evidence refs are
global G1/G2/G3/GL/G7 recall/freshness artifacts.

Why this fails:

- A global search-health artifact does not prove the missed-path question for a
  specific blocker, construct, or conversion attempt.
- This can normalize a domain ceiling or abstention before the relevant search
  frontier was measured.
- This is P03/P10/P25.

Forbidden repair:

- Adding more global evidence refs to the G8 answer.
- Treating "no ceiling repair flag" as equivalent to "recall proven".

Required repair:

- G8 answers must distinguish corpus-level search health from
  conversion-attempt-specific search adequacy.
- For a pinned conversion or abstention claim, G8 must cite the exact
  SearchRequest, search ledger, selected/rejected candidates, index versions, and
  measured misses.

### 10. G6 audit can still be authored instead of observed

`src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py` has audit fields for
`rejected_tool_names`, `selected_evidence_refs`, and `rejected_branch_refs`, but
current build paths still assign constants such as `("unbounded_web_search",)`
and synthetic rejected branch refs around lines 1349-1354 and 1652-1654. The
no-client path also constructs blocked branches from builder state around lines
2392-2402.

Why this fails:

- An orchestration audit must be derived from the actual tool-loop result, not
  from a builder's idea of what probably would have been rejected.
- Synthetic rejected branches create a false T4/T6 memory surface and can make
  G6 look governed while no real alternative was observed.
- This is P02/P10/P15.

Forbidden repair:

- Adding more plausible rejected tool names.
- Counting selected evidence refs that were not returned by the traced gateway or
  resolved through G5/GX reference resolution.

Required repair:

- G6 audit artifacts must be built from traced tool-loop events with event ids,
  selected/rejected tool calls, selected/rejected candidate refs, and resolver
  outcomes.
- If no tool loop ran, the audit status is `not_measured` or a typed blocker, not
  a populated synthetic audit.

### 11. Published artifact corrections must not be silent overwrites

`architecture/policy_design_case/layer3_g1_hardcode_strangle_delta.json` has
already carried claims about hardcode deletion/disablement while the underlying
runtime still contained `KNOWN_CONSTRUCTS` and
`REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS` paths. Even when the current file is
later regenerated with better issue codes, the historical false claim must be
retracted or corrected explicitly.

Why this fails:

- A governed artifact that asserted an untrue status is itself governance debt.
- Silent regeneration erases the failure memory that should prevent recurrence.
- This is P11/P07/P10.

Forbidden repair:

- Rewriting the JSON and treating the correction as if the original claim never
  existed.

Required repair:

- Add a correction/retraction record that names the artifact, false claim,
  replacement status, producer responsible for the correction, and replay evidence
  proving the new claim.

### 12. Demand-pull is still underspecified

G5 currently can build a demand-pull attempt using hardcoded refs such as
`s3-demand-pull://ua-msme/first-proving-ground` in
`layer3_proving_ground_conversion.py` around lines 941-945. G7 artifacts also
carry this style of demand-pull ref. But `grounded_abstention` requires a valid
demand-pull attempt, and the plan must define what makes such an attempt real.

Why this fails:

- If demand-pull refs can be authored inline, abstention can be laundered through
  a fake demand signal.
- If no valid demand-pull producer is defined, grounded abstention may be blocked
  forever even after search is measured.

Forbidden repair:

- Treating any `s3-demand-pull://...` string as valid demand-pull evidence.

Required repair:

- Demand-pull must be a persisted artifact with producer ref, accountable
  principal or request source, timestamp, input request, replay key, and resolved
  consumer path into G5/G6/G7.

### 13. The recurring bad-fix pattern

The repeated failure is not "missing code". The repeated failure is adding code
that improves one local symptom while leaving an older authority path reachable.

The following repair styles are forbidden across all GX tasks:

| Bad repair style | Concrete smell | Why it is banned |
| --- | --- | --- |
| Wrong literal -> right literal | Changing fertilizer to credit/survival inside a runtime default. | Still requires code edits for domain growth. |
| Shape check -> local deref only | Adding `_g4_g1_*` deref while G4 still consumes default requests. | Bridges one family but leaves orchestration synthetic. |
| Hardcoded positive -> parameterized positive | Passing `grounding_closure_outcome` into a summary while health still says pass. | Moves the assertion; does not make it measured. |
| Blocker -> readiness pass | Suppressing issue codes when outcome is `unchanged_blocker`. | Converts known incompleteness into green readiness. |
| Placeholder -> better placeholder | Replacing `sha256:111...` with another fake digest. | Replay remains impossible. |
| Global seed health -> case adequacy | Citing broad recall artifacts for a specific blocker. | Missed-path risk is not measured at the relevant grain. |
| Negative fixture only | Proving validators reject bad JSON while production builders still author bad inputs. | Tests the schema, not runtime behavior. |
| Rebuild over subordinate | Building a parallel search engine, G2 pipeline, or agent while the real one (Asset Registry) sits unwired. | Duplicates the engine and leaves the jewel dead — the exact G1-hollow pattern. |
| Smart-component pass | Treating a `scientist_policy_design` bundle as authority because the DAG is sophisticated. | Bundle authority requires a producer-root chain to measurement, not DAG complexity. |

## Task -1 - Clean Baseline And Signal Isolation — DONE (see worktree caveat)

Do not start GX behavior work on a dirty or already-red baseline. Otherwise the
first GX red test is indistinguishable from existing drift, uncommitted artifact
churn, or unrelated slice failures.

Required actions:

- Record `git status --short` in a baseline note before any GX change.
- Commit, park, or explicitly exclude unrelated worktree changes before GX Task 0.
- Run and record the currently known failing Layer 3 tests and readiness checks.
- Regenerate or explicitly quarantine drifted generated artifacts before adding
  new GX diagnostics.
- Reconcile slice-plan statuses so active/completed state matches actual artifacts.
- Identify any atlas or non-Layer-3 work mixed into the branch and move it out of
  the GX closeout surface.
- Record ownership for unresolved G0 debts: triage coverage for all inventory
  sources/assets, binary lex quarantine status, and G0 manifest/runtime drift.
  Either fix them in Task -1 or link to a live plan that blocks GX closeout if it
  remains unresolved.

Acceptance:

- The branch has a clean or intentionally scoped worktree before Task 0 begins.
- The baseline note lists every pre-existing red check and dirty artifact.
- The first GX validator failure can be attributed to a GX red fixture, not to
  unrelated branch hygiene.
- G0 residual debts are either closed or explicitly carried as blockers with
  owner, artifact ref, and closeout condition.

## Task 0 - Red Baseline, Recompute Guard, And Runtime Literal Kill Switch — DONE

Add a Layer 3 hardening validator and tests before changing runtime behavior.

Required artifacts:

- `tools/quality/validation/check_policy_design_case_layer3_gx_hardening.py`
- `architecture/policy_design_case/layer3_gx_baseline_note.json`
- `architecture/policy_design_case/layer3_gx_runtime_literal_lint.json`
- `architecture/policy_design_case/layer3_gx_reducer_integrity_report.json`
- `architecture/policy_design_case/layer3_gx_positive_status_provenance.json`
- `architecture/policy_design_case/layer3_gx_producer_registry.json`
- `architecture/policy_design_case/layer3_gx_producer_root_chain_report.json`
- `architecture/policy_design_case/layer3_gx_measurement_replay_report.json`
- `architecture/policy_design_case/layer3_gx_persisted_status_recompute_drift.json`
- `architecture/policy_design_case/layer3_gx_status_vocabulary_delta.json`
- `architecture/policy_design_case/layer3_gx_correction_retraction_log.json`
- `architecture/policy_design_case/layer3_gx_independent_audit_sample.json`
- `architecture/policy_design_case/layer3_gx_validation_authority_boundary.json`
- `architecture/policy_design_case/layer3_gx_expected_red_checks.json`
- `architecture/policy_design_case/layer3_gx_human_approval_receipts.json`
- `tests/repo_quality/tools/test_policy_design_case_layer3_gx_hardening.py`

Implementation requirements:

- The validator recomputes persisted positive statuses from dereferenced reducer
  inputs and compares recomputed output hashes to persisted artifact hashes.
- Every positive persisted Layer 3 status must include `produced_by.reducer_id`,
  `produced_by.reducer_version`, `produced_by.rule_version`,
  `produced_by.input_hashes`, and `produced_by.output_hash`.
- A positive status without reducer provenance fails, even if it contains no
  forbidden literals.
- The validator builds a producer graph from `producer_ref` fields, classifies
  every producer as `measurement`, `external_request`, `derivation`, or
  `test_fixture`, and walks every positive status to valid roots.
- A production positive status fails if any supply-side fact terminates in
  `derivation`, `test_fixture`, or an untyped producer without measurement roots.
- A production positive status fails if demand-side facts lack an
  `external_request` or measurement root.
- The validator replays all measurement roots on the provisional pinned route and
  a deterministic rollout sample, then compares replayed output hashes to
  persisted measurement hashes.
- Measurement roots without executable replay contracts are treated as
  `not_measured` or typed blockers.
- The validator emits the validation authority boundary so legacy-green
  non-migrated slices cannot count as GX-green.
- Runtime literal lint uses AST, not only regex. It flags string literals used as
  `status=`, `promotion_state=`, `conversion_outcome=`, maturity/admission
  keywords, source-contract/promotion/evidence inputs, and positive summary keys
  outside approved reducer/type/test files.
- The AST pass flags production builders that discard inputs, such as `del
  repo_root`, and then return models or dicts containing status fields.
- Digest lint rejects repeated-character hashes such as `sha256:(.)\1{7,}`,
  non-hex sha256 values, and incomplete sha256 values.
- The scan scope includes `src/polisyos/core`, `src/polisyos/runtime`,
  `tools/quality/validation`, generated Layer 3 artifact builders, and relevant
  tests. Do not scope it only to `src/polisyos/runtime`.
- The validator fails if a positive closure/admission/promotion/conversion
  status is authored outside approved reducer/type/test locations.
- The validator fails if any old fallback path remains after the new producer
  exists. For `KNOWN_CONSTRUCTS` and
  `REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS`, "unreachable" is not enough:
  the definitions and re-exports must be deleted or moved into governed data.
- The validator must not accept comments, TODOs, or deprecation notes as
  closure.
- The validator must treat every example in "Current Code-Grounded Failure
  Examples" as a red baseline until a narrower test or lint rule supersedes it.
- Allowlist additions have a fixed budget. Adding an allowlist entry fails CI
  unless the PR includes explicit human approval, owner, reason, expiration, and
  removal condition.
- Expected-red mode is allowed only before provisional Task 12. It must list
  every known GX failure by name in `layer3_gx_expected_red_checks.json`.
  Removing or weakening a check to get green is forbidden; the check leaves
  expected-red only when the named producer/resolver/reducer/artifact is wired.
- Closeout requires an independent audit sample: select at least five positive
  statuses or all positive statuses if fewer than five, trace producer roots by
  hand in `layer3_gx_independent_audit_sample.json`, and for measurement roots
  physically verify backing rows by opening the referenced DuckDB/store/index.
  The manual audit receipt must be approved by `deniskopylov` through the required
  approval channel.

Acceptance:

- The initial test must fail on current G1/G4/G5 overclaims.
- The final validator must be included in the Layer 3 readiness command set.
- A new forbidden literal in a runtime builder must fail CI.
- A PR may not close Task 0 while any listed bad-fix pattern remains reachable
  from production readiness/build paths without a failing diagnostic.
- A hand-edited persisted positive status fails recompute-and-compare even when
  the JSON schema is valid.
- A persisted synthetic G2 method candidate with producer ref and content hash but
  no measurement-root ancestry fails producer-root validation.
- A positive status whose producer chain is derivation-only fails even when
  recompute-and-compare passes.
- A measurement root with a copied corpus hash but no replayable query/probe fails
  measurement replay.
- A legacy per-slice validator green status has no GX closeout authority until the
  boundary artifact marks the slice `gx_hardened`.
- Before provisional Task 12, red GX checks are allowed only when named in
  expected-red; after provisional Task 12, new expected-red entries require
  stop-and-review.

## Task 0A - Minimal Data Home Before Literal Removal — DONE

Create the smallest persisted data home needed to move domain values out of
runtime code before deleting literals. Do this before Task 1. Do not strand the
pinned path between "literals removed" and "data exists."

Required artifacts:

- `architecture/policy_design_case/layer3_gx_pinned_request.json`
- `architecture/policy_design_case/layer3_gx_concept_alias_seed_rows.json`
- `architecture/policy_design_case/layer3_gx_scope_seed_rows.json`
- `architecture/policy_design_case/layer3_gx_demand_pull_request.json`

Required contents:

- Pinned request payload with case/request identifiers, requested constructs,
  scope, authority purpose, and expected consumer path.
- Concept/alias rows for the pinned constructs and broad query terms, owned by
  data artifacts rather than runtime Python.
- Scope rows for entity type, population, geography, modality, source-family
  aliases, and validity limits.
- Demand-pull request artifact with producer/source, timestamp, accountable
  principal or request source, replay key, and G5/G6/G7 consumer path.
- Producer records marking pinned request, scope, and demand-pull as
  `external_request` roots.
- Alias rows marked `unverified` until measurement resolves them to corpus rows.

Acceptance:

- G1/G2/G4/G5 can read pinned request/scope/concept/demand values from persisted
  artifacts without runtime default request helpers.
- Removing a row from this data home changes the reducer outcome to a typed
  blocker and does not re-enter a code fallback.
- The data home is sufficient to run the vertical pinned route through reducers,
  even if the final outcome is blocked.
- The data home cannot assert corpus supply facts. It may state the demand, not
  that evidence exists.

## Task 1 - No Literal Domain Closure Rule — ROLLOUT (pending; closes expected-red)

Remove domain logic from runtime builders and validators. Domain values may be
loaded from data manifests, request payloads, temp test databases, or governed
concept/alias graph rows, but runtime code must not branch on them.

Required changes:

- Delete runtime default requests and default rows that encode a particular
  construct or case as logic.
- Replace hardcoded scenario-family mapping use with data-owned concept/scope
  lookup.
- Replace hand-authored positive statuses with reducer outputs.
- Replace placeholder source design records and repeated-character digests with
  missing-artifact blockers.
- Delete `KNOWN_CONSTRUCTS` and
  `REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS` definitions/re-exports or convert
  them into governed data rows consumed through the same resolver as other
  concept/scope records.
- Migrate Layer 2 and core consumers of
  `REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS` and `KNOWN_CONSTRUCTS` to governed
  data rows. Do not leave compatibility re-exports behind.
- Add a correction/retraction record for any previously published governed
  artifact that asserted deletion, disablement, calibration, promotion, or
  grounding that was not true when dereferenced.

Hard blockers:

- No "temporary fallback" to legacy mappings.
- No "shadow default" used by readiness writers.
- No "fixture only" row counted by a production readiness path.
- No case-specific exception in a validator.
- No inline reducer input in production build/readiness paths.

Acceptance:

- Runtime literal lint passes with a narrow allowlist only for DTO Literals,
  reducer truth tables, and tests.
- Removing the governed data row for a construct causes a typed blocker, not a
  code fallback.
- Adding a governed data row changes behavior without editing runtime code.
- The correction/retraction log names every corrected false governed artifact and
  the recomputed replacement status.
- Layer 2 readiness and `test_capability_resolver`-class consumers pass after the
  mapping removal or fail with a migration blocker owned by this plan.

## Task 2 - Universal Search Contract — PARTIAL (G1 done; G2/G3/GL pending)

Create one reusable search contract used by G1, G2, G3, GL, G6, G7, and G8.
Slices may add adapters, but they may not invent incompatible search semantics.

Required contract:

```text
SearchRequest:
  request_id
  query_text
  construct_refs
  intent
  required_layers
  authority_purpose
  allowed_modes
  budget
  rule_version

SearchCandidate:
  candidate_ref
  source_layer
  match_mode
  score
  evidence_refs
  limitation_refs
  authority_boundary
  may_not_use_for

SearchLedger:
  request_ref
  query_plan
  corpus_ref
  corpus_path
  corpus_snapshot_hash
  corpus_kind
  indexes_used
  index_version_refs
  candidates
  rejected_candidates
  no_hit_frontier
  incompleteness
  replay_key
  replay_command
  replay_expected_output_hash
```

Required implementation:

- Put the contract in a canonical shared runtime/search or core contract module.
- Adapt G1 DCAT, G2 SKG, G3 IR, and GL legal KG to emit the same ledger shape.
- Preserve source-specific details in typed payloads, not in separate semantics.
- Record exact, alias, lexical, semantic, relational, and derived match modes.
- Record query expansion traces and index freshness.
- Make `replay_key` executable by linking it to a replay command, parameters,
  environment, corpus snapshot, and expected output hash.
- Production search-health artifacts must name the canonical corpus path, corpus
  snapshot hash, configured store path, and whether the run used `canonical` or
  `bounded_surrogate` data.
- If the configured store is not the canonical corpus for the production
  readiness run, the status is `bounded_surrogate`, never a full pass.

Acceptance:

- G1, G2, G3, and GL validators all consume the common `SearchLedger` fields.
- G8 can audit search health from common fields without slice-specific parsing.
- A search ledger with candidates but no admission cannot close any slice.
- A temp-store test can prove engine generality, but cannot satisfy production
  search health unless the canonical corpus path and snapshot hash match.
- A search ledger with a decorative replay key but no executable replay command
  cannot support a positive search-health claim.

## Task 3 - Separate Search, Admission, And Closure — PARTIAL (vertical done; rollout slices pending)

Refactor every Layer 3 slice so search, admission, materialization, and closure
are different records with different reducers.

Required records:

- `SearchLedger`
- `AdmissionResult`
- `MaterializedArtifactRecord`
- `ResolvedRef`
- `ClosureDecision`

Slice-specific rules:

- G1: DCAT candidate is not a `SourceContract`.
- G2: SKG edge is not `ForecastSupport`.
- G3: IR proof candidate is not proof authority.
- GL: legal KG hit is not legal authority.
- G4: promotion input is not governed promotion.
- G5: blocker explanation is not grounded abstention.
- G8: metric reading is not domain-ceiling authority.
- Admission artifact: authored data row is not admission; it must be a derivation
  output from a conformance/admission producer with measurement roots.

Acceptance:

- Each slice has a negative test where search succeeds, admission fails, and
  closure remains blocked.
- Each slice has a negative test where admission succeeds but materialized
  artifact is missing, and closure remains blocked.
- Every downstream consumer checks the upstream materialized artifact or
  `ResolvedRef`, not only a summary count.
- A manually inserted production admission row fails producer-root validation even
  when its schema is valid.

## Task 4 - Reducer-Only Status And Closure — DONE (8 reducers in layer3_status_reducers.py)

All closure/admission/promotion/conversion statuses must be produced by pure
reducers. Builders may assemble inputs; they may not write positive outcomes.

Required reducers:

- `reduce_g1_source_grounding_closure`
- `reduce_g2_forecast_admission`
- `reduce_g3_proof_authority`
- `reduce_gl_legal_authority`
- `reduce_g4_promotion_state`
- `reduce_g5_conversion_outcome`
- `reduce_g7_region_closure`
- `reduce_g8_domain_vs_search_ceiling`

Reducer requirements:

- Pure function over typed lower-level artifacts.
- Exhaustive truth table in tests.
- Returns status, blocker refs, limitation refs, input refs, and rule version.
- No filesystem reads inside reducers.
- No generated positive status when required input refs are missing.
- Returns producer provenance for every positive result: reducer id/version,
  rule version, input hashes, output hash, and vocabulary status id.
- Rejects inline inputs that do not carry producer refs and content hashes, except
  in explicit test fixtures.
- Rejects positive closure when the producer-root report marks any required
  supply-side input as derivation-only, untyped, test-only, or unverified.

G1 minimum truth table:

| Inputs | Outcome |
| --- | --- |
| configured store is not canonical for production readiness | bounded surrogate / typed blocker; cannot close grounding |
| source contract bindings exist and validate | grounded or observed according to binding status |
| zero bindings, measured no-hit, recall/freshness pass, canonical store, overlay injection pass | grounded abstention candidate only if vocabulary ADR approved; otherwise typed blocker with vocabulary issue |
| zero bindings, recall/freshness fail or not measured | search ceiling repair required |
| candidate exists, admission blocked | typed blocker |
| artifact ref missing | fail |

The G1 reducer may emit only the statuses approved by the vocabulary delta. If
`grounded_abstention_candidate` is not approved, the same inputs must produce a
typed blocker that tells G5 the candidate transition is unavailable. G5 is the
only reducer allowed to convert an approved candidate plus demand-pull and
cross-slice checks into `grounded_abstention`.

Acceptance:

- Current contradiction `0 bindings + grounded_or_uncertain` fails.
- Current contradiction `unchanged_blocker + readiness pass with suppressed
  dependency issues` fails or is explicitly marked blocked/not-ready.
- Readiness manifests report reducer outputs and cannot override them.
- `layer3_gx_reducer_integrity_report.json` enumerates every positive Layer 3
  status and proves its reducer provenance.
- Reducer provenance is linked to producer-root-chain validation; reducer
  provenance alone is not sufficient.

## Task 5 - Required Reference Resolver — DONE (required_reference_resolver.py)

No cross-slice string ref may count until dereferenced by a shared resolver.

Required contract:

```text
ResolvedRef:
  ref
  exists
  artifact_path
  json_pointer
  content_hash
  producer_ref
  producer_type
  producer_root_refs
  produced_at
  schema_version
  rule_version
  authority_boundary
  issue_codes
```

Required implementation:

- Resolve JSON refs, TOML refs, CAS refs, generated artifact refs, and manifest
  refs through one canonical resolver.
- Fail closed on missing pointer, missing artifact, stale content hash, schema
  mismatch, rule mismatch, authority-boundary mismatch, or placeholder digest.
- Fail closed on missing producer ref for authority-bearing inputs.
- Fail closed on invalid producer type/root chain for authority-bearing inputs.
- Treat repeated-character, non-hex, malformed, or incomplete sha256 digests as
  blockers.
- G4 must dereference G1/G2/G3/GL refs before building `grounded_contract_set`.
- G5 must dereference G4 promotion records and grounded evidence refs before
  counting evidence.
- G8 must dereference metric source refs before answering open questions.
- G6 must dereference selected/rejected evidence refs before counting audit
  branches or demand-pull evidence.

Acceptance:

- A ref like `...#bindings/<missing>` fails G4.
- G5 cannot report a grounded evidence count for a missing G1 binding.
- A manifest-only source design record cannot be promoted.
- Placeholder or repeated-character digests are blockers, never warnings.
- Inline producer-less inputs fail even when their shape matches the DTO.
- Persisted derivation-only inputs fail when used as supply-side evidence for a
  positive status.

## Task 6 - Data-Mutation Free-Growth Tests — DONE (mutation coverage and report wired)

Replace fixture-only free-growth tests with mutation tests over temp stores.
Temp-store tests prove search generality. They do not prove production readiness
unless paired with a canonical-corpus run.

Required test pattern:

1. Create a temp DCAT/SKG/IR/legal KG.
2. Insert a new metric, edge, proof, or legal threshold.
3. Run the real search service with no code changes.
4. Verify the new candidate appears in a replayable search ledger.
5. Verify the candidate does not become authority without admission.
6. Insert a governed admission/materialization artifact.
7. Verify the reducer changes closure from blocked/abstention to admitted where
   allowed.
8. For blocker-specific recall, run the canonical corpus plus isolated overlay
   seed injection and verify the injected seed is found without counting it as
   grounding.

Required tests:

- G1 DCAT metric-binding insertion.
- G2 SKG edge insertion plus no calibration.
- G2 SKG edge insertion plus governed method/calibration admission.
- G3 IR proof-candidate insertion plus no certificate.
- GL legal-threshold insertion plus temporal/reissue gate.
- G4 governed upstream artifact insertion and promotion.
- G5 conversion changed only by reducer inputs.
- G8 pinned-case search-health changed by case-specific diagnostic data.
- Canonical corpus run for the pinned request, with corpus path and snapshot hash
  recorded in search-health artifacts.
- G1 canonical-corpus overlay injection for the pinned no-hit construct.

Acceptance:

- Adding data changes candidates without runtime code edits.
- Removing admission data blocks closure.
- Tests fail if any runtime domain literal is required to find the new data.
- Production readiness remains `bounded_surrogate` if it only ran against a temp
  store or construct-scoped cache.
- Overlay-injected rows can support recall adequacy only; they cannot create a
  source contract, admission artifact, promotion, or grounded conversion.

Completed evidence:

- Added Task 6 slice tests for G4 governed upstream artifact insertion, G5
  reducer-input-only conversion changes, and G8 case-specific search-health
  diagnostics.
- Strengthened G2 Task 6 replay assertions and validator authority-boundary
  coverage so search ledgers must explicitly deny `search_hit_as_authority`.
- Preserved existing G1/G2/G3/GL mutation tests and G1 canonical overlay recall
  test as the required temp/canonical proof surface.
- Added and generated
  `architecture/policy_design_case/layer3_gx_data_mutation_free_growth_test_report.json`
  with all required rows passing, no missing test refs, canonical snapshot-hash
  coverage, and overlay/temp authority boundaries marked non-authoritative.

Verification:

- `uv run pytest tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py tests/unit/runtime/quality/test_layer3_g3_analytics_search.py tests/unit/runtime/quality/test_layer3_gl_legal_mandate_search.py tests/unit/runtime/quality/test_layer3_g4_promotion_gate.py tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py tests/unit/runtime/quality/test_layer3_status_reducers.py tests/repo_quality/tools/test_policy_design_case_layer3_gx_hardening.py -k "task6 or requires_search_hit_authority_denial" -q`
  passed with 21 tests.
- `uv run ruff check ...` passed for all Task 6 touched production/test files.
- `uv run python tools/quality/validation/check_policy_design_case_layer3_gx_hardening.py --repo-root . --write --output-format json`
  wrote the Task 6 report; the overall GX hardening validator still exits
  expected-red because non-Task-6 provenance/recompute/legacy-boundary blockers
  remain.

## Task 7 - Concept And Alias Graph — DONE (SKG wiring plus guarded overlay)

Wire the **existing** SKG canonicalization, then add a thin data-owned overlay
for gaps. L2 already holds `ac_skg_variables` (~55k canonicalized variables) and
`ac_skg_context_attributes` (~200k) — these are `measurement`-root aliases. Do
not introduce a fresh graph that re-derives them, and do not add
construct-specific branches to G1/G2/G3/GL. The overlay carries only aliases the
SKG lacks, each `unverified` until a measurement producer resolves it to corpus
rows.

Required fields:

```text
concept_ref
aliases
metric_ids
variable_names
source_layer_refs
jurisdiction_constraints
validity_limits
producer_owner
producer_type
verification_status
resolved_corpus_row_refs
rule_version
```

Search requirements:

- Query expansion must be recorded in the search ledger.
- Exact ids, aliases, lexical matches, semantic candidates, and source-layer
  joins must be separate match modes.
- Semantic/HNSW disabled state must be explicit in the ledger and search-health
  report.
- A broad query must find governed aliases without code changes.
- Authored aliases start as `unverified`; a measurement producer must resolve them
  to corpus rows before they can support recall/admission/closure.

Acceptance:

- A broad query finds canonical metric candidates through data-owned aliases.
- If alias graph is absent, search reports degraded/limited recall, not pass.
- New aliases can be added by data mutation tests without runtime edits.
- An alias row with no measured corpus resolution broadens search but cannot
  satisfy a positive recall-health claim.

Completion notes (2026-06-13):

- `layer3_gx_concept_alias_graph.json` is now built by preferring existing SKG
  measurement rows from `ac_skg_variables` / `ac_skg_context_attributes` when
  present, with data-home aliases remaining an `unverified` overlay.
- The alias graph loader blocks semantically invalid authority states:
  `measured` rows require measurement-owned corpus resolution refs, and
  `unverified` rows may not carry resolution refs.
- G1 query expansion records exact, alias, lexical, semantic, and relational
  source-layer join modes; search-health now carries explicit semantic/HNSW
  state.
- Unverified aliases can broaden search and return candidates, but G1 positive
  recall now requires measured alias-graph corpus resolution.

## Task 8 - G2 Method And Forecast Admission Pipeline — MOVED TO GY

The stages this task once specified (SKG search → method binding → Foundry
selection → S10 prerequisite → calibration → ForecastSupport → handoff)
**already exist** as `scientist_policy_design` DAG nodes
(`build_literature_prior` → `build_method_catalog_snapshot` →
`run_causal_readiness` → `counterfactual_identification_gate` → `run_simulation`;
see Asset Registry). Building a parallel G2 pipeline is the "rebuild over
subordinate" anti-pattern. The work is reframed as **subordination** of those
nodes through a DAG-bundle→port adapter, with producer-root validation, and lives
in `GY-engine-subordination.md`. GX does not build a forecast producer; the GX
vertical (Task 12) honestly stays at a no-G2 blocker/abstention until GY wires the
DAG. The hard blockers (no synthetic method candidate as authority; calibrated
maturity reducer-only with measurement-root ancestry) are preserved in GY.

## Task 9 - G4 And G5 As Waist Court, Not Fact Producers — DONE (GX vertical; multi-family stays in GY)

G4 and G5 must judge upstream artifacts. They must not synthesize evidence rows,
source contracts, design records, or promotion facts.

This task stays in GX (the court is producer-agnostic and the vertical needs it).
In GX the governed inputs are the data-home request plus G1 source-contract
bindings; the **richest** governed input — the `scientist_policy_design` bundle —
is wired in GY. G4/G5 judge whatever upstream resolves; they never depend on a
specific producer existing.

G4 requirements:

- Read promotion requests from governed inputs, not default rows.
- Dereference every upstream contract ref.
- Build promotion state only through `reduce_g4_promotion_state`.
- Block source-only rows from satisfying causal/effect/legal scopes.
- Treat manifest-only design records, placeholders, and missing payloads as hard
  blockers.

G5 requirements:

- Read G1/G2/G3/GL/G4 resolved refs.
- Count evidence only after dereference and independence collapse.
- Build conversion only through `reduce_g5_conversion_outcome`.
- Never suppress dependency issue codes because the outcome is unchanged.
- `grounded_abstention` requires measured search, demand-pull attempt, grounded
  reason, and no missing-ref contamination.
- Demand-pull attempt records must be produced artifacts with producer ref,
  timestamp, accountable request/source, replay key, and dereferenced consumer
  path. A bare `s3-demand-pull://...` string is unresolved evidence.

Acceptance:

- G4 fails when G1 grounded source contract bindings are empty.
- G5 reports no grounded evidence for phantom refs.
- `unchanged_blocker` cannot produce green readiness if required dependencies
  are failing.
- G5 can reach `grounded_abstention` only through the reducer truth table.
- A missing or unresolved demand-pull artifact blocks grounded abstention instead
  of being filled by a default ref.

Completed on 2026-06-13:

- G4 promotion records and weakest-boundary composition now carry
  `reduce_g4_promotion_state` provenance; positive promotion state is reducer
  authored, not manually assigned.
- G5 conversion eligibility now calls `reduce_g5_conversion_outcome`, preserves
  dependency issue codes even when the outcome remains `unchanged_blocker`, and
  carries reducer provenance on the ledger.
- G5 demand-pull records preserve GX data-home producer/timestamp/source/
  replay/consumer-path metadata, and bare `s3-demand-pull://...` refs fail
  grounded-abstention eligibility.
- GX now writes `layer3_gx_g4_g5_dereference_waist_court_report.json` as a
  diagnostic waist-court surface with explicit `may_not_use_for` authority
  boundaries. Its status remains `partial` by design because multi-family
  producer subordination belongs to GY, not GX.

## Task 10 - G6 Actual Tool-Loop And Demand-Pull Audit — MOVED TO GY

The agent platform already exists (`scientist/agent`: PI/drafter/supervisor,
tool-loop, `vector_memory`); G6 must report what it actually did, not synthesize
rejected tools/branches/evidence. This is subordination of the existing agent
plus an event-backed audit, and depends on the GY DAG/route producers, so it
lives in `GY-engine-subordination.md`. G6 is not on the GX vertical
(G1→G4→G5, no agent). The fix (event-backed audit, `not_measured` when no loop
ran, resolver-checked evidence refs, persisted demand-pull records) is preserved
in GY.

## Task 11 - G8 As Auditor, Not Optimism Normalizer — DONE (auditor fail-closed)

G8 must audit search, demand, governance, and domain ceiling claims. It must not
convert global seed health into pinned-case health.

Required distinctions:

- Search health for seed corpus.
- Search health for pinned case.
- Search health for current blocker.
- Domain ceiling claim.
- Search ceiling repair.
- Governance stall.
- Demand inertia.

Required implementation:

- G8 open-question answers must cite blocker-specific diagnostics.
- G8 must fail or block if G1/G2/G3/GL search health is only seed-level while
  the current blocker is unmeasured.
- Domain ceiling cannot be claimed until search frontier, freshness, admission,
  and dereferenced artifacts all pass for the relevant blocker.
- G8 conformance must include negative controls for hidden optimism in metrics.
- G8 must cite reducer provenance for every positive answer status.
- G8 must classify search answers separately for corpus health, pinned request,
  current blocker, and production readiness.

Acceptance:

- Passing seed recall with pinned-case no-hit is not "currently healthy" unless
  the pinned no-hit is measured and recorded as abstention/blocker evidence.
- Governance stall and demand inertia cannot be hidden behind pass statuses.
- G8 readiness fails on manifest/runtime drift.
- `answered_currently_healthy` fails when evidence refs are global-only and the
  blocker-specific search ledger is absent.

Completed on 2026-06-13:

- G8 now emits a first-class search-health classification separating seed
  corpus, pinned request, current blocker, and production-readiness status.
- G8 domain-ceiling gating now fails closed unless blocker-specific search
  frontier, freshness, admission, and dereferenced artifact statuses all pass.
- The current GX state is intentionally `search_ceiling_repair_required`:
  seed/global search refs are visible, but current-blocker search remains
  `unmeasured`, so `answered_currently_healthy` is blocked rather than
  normalized from global seed health.
- Positive open-question answers now carry reducer-style `produced_by`
  provenance with input hashes and output hash.
- G8 conformance now includes hidden-optimism negative controls for global seed
  health masquerading as current-blocker health, absent blocker-specific ledger,
  domain-ceiling precondition gaps, and missing positive-answer provenance.
- The G8 readiness manifest now reports top-level `fail` when runtime/audit
  issues exist, even with zero manifest drift; this is an honest blocker for
  final Task 12, not a Task 11 incompleteness.

## Task 12 - Pinned Route Outcome Run — DONE (final rerun: search_ceiling_repair_required)

Run the pinned case through the hardened vertical route twice: first as a
provisional milestone immediately after the vertical G1 -> G4 -> G5 route is
wired, and again at final closeout. This task is the value check for GX. It must
produce measured, reducer-authored statuses for the pinned flow on canonical
corpora.

Required route:

```text
layer3_gx_pinned_request
-> G1 canonical DCAT SearchLedger
-> G1 measured recall/freshness
-> G1 admission/materialized source-contract refs or no-hit blocker
-> G4 promotion request from persisted input
-> G4 reducer-produced promotion/blocker
-> G5 resolved evidence/demand-pull inputs
-> G5 reducer-produced conversion outcome
-> GX/G8 blocker-specific audit answer
```

The provisional run must at minimum produce the G5 reducer outcome plus a GX
blocker-specific audit record. The final run must also pass through the repaired
Task 11 G8 open-question/audit surface.

Allowed outcomes:

- `grounded_limited`, only if reducer-produced from measured inputs and
  dereferenced governed artifacts
- `grounded_abstention`
- `search_ceiling_repair_required`
- a typed blocker with exact missing producer/resolver/corpus/demand/materialization
  refs

Hard blockers:

- No task may force useful-design credit.
- No task may complete with only `not_measured` statuses.
- No task may treat temp-store free-growth proof as canonical pinned-route proof.
- No task may accept a persisted status whose recomputed output hash differs.
- No task may reject a real `grounded_limited` outcome merely because the expected
  outcome was abstention or a blocker.

Acceptance:

- The provisional run happens immediately after the vertical G1/G4/G5 route is
  wired and before G2/G6/G8 rollout tasks.
- The pinned-route report names every reducer called, its input hashes, output
  hash, rule version, and persisted artifact refs.
- The outcome is produced by G5 and, for final closeout, G8 reducers from measured
  inputs, not authored in a readiness manifest.
- If the outcome is blocked, it names the next concrete missing producer or
  corpus/search/resolver issue.
- The run is repeatable from the persisted artifacts and canonical corpus
  snapshot refs.
- The final run compares against the provisional run and explains every changed
  reducer input, producer root, and status.

Implementation closeout:

- Provisional run remains persisted as
  `architecture/policy_design_case/layer3_gx_provisional_pinned_route_outcome_report.json`
  with G1/G4/G5 reducer calls and typed blocker outcome from G5.
- Final run is persisted as
  `architecture/policy_design_case/layer3_gx_final_pinned_route_outcome_report.json`
  with G1/G4/G5 plus `reduce_g8_domain_vs_search_ceiling` reducer calls, input
  hashes, output hashes, rule versions, and persisted refs.
- Final blocker-specific audit is persisted as
  `architecture/policy_design_case/layer3_gx_final_blocker_audit_record.json`
  and consumes the Task 11 G8 open-question ledger, domain-vs-search ceiling
  gate, cross-metric diagnosis, audit surface, and closeout consumer gate.
- Current final outcome is `search_ceiling_repair_required`, not a useful-design
  or domain-ceiling claim: G8 current blocker and pinned-request search health
  remain `unmeasured`, and the blocker names
  `layer3_g8_blocker_specific_search_diagnostic_missing`.
- `layer3_gx_expected_red_checks.json` now records
  `final_task12_complete: true`; remaining GX expected-red items are tracked as
  post-final hardening blockers, not Task 12 incompleteness.

## Follow-On G7 Rollout Slice

`reduce_g7_region_closure` is declared in this plan because region widening must
eventually share the reducer/provenance/search-health rules. It is not part of
the minimal shippable set.

Required follow-on:

- Create a separate G7 rollout slice after provisional Task 12.
- Wire G7 region closure through the same resolver, producer-root chain,
  measurement replay, canonical-corpus search health, and validation authority
  boundary.
- Migrate existing G7 demand-pull and regional matrix artifacts away from inline
  refs and legacy per-slice green statuses.

Acceptance:

- Until that follow-on slice is complete, G7 is marked
  `legacy_validator_no_gx_authority` or `blocked_by_gx_migration` in the
  validation authority boundary.
- G7 cannot count toward GX domain-ceiling or regional breadth claims before the
  follow-on slice reaches `gx_hardened`.

## Execution Order

Do not parallelize late-stage slices before the lower gates are repaired. The
order is mandatory:

1. Task -1: clean or explicitly scope the baseline and record G0/process debt.
2. Task 0A: create the minimal persisted data home for pinned request, concept,
   scope, and demand-pull values.
3. Task 0: add recompute-and-compare validator, AST lint, provenance inventory,
   digest checks, vocabulary delta, and red tests.
4. Task 5: add the shared resolver early enough that no slice needs local
   one-off dereference helpers.
5. Task 4: add reducer-only closure/admission/promotion/conversion decisions with
   provenance output.
6. Task 2: add the universal search contract and canonical-corpus search-health
   fields.
7. Vertical hardening pass: wire only the pinned G1 -> G4 -> G5 route through the
   resolver, reducers, measured search, and data-home values.
8. Provisional Task 12: run and persist the first pinned-route reducer outcome.
   Stop and reassess if this cannot run.
9. Task 1: delete runtime domain literals, legacy mappings, placeholder refs, and
   inline reducer inputs only after the data-home and reducers exist.
10. Task 7: add concept/alias graph and query expansion traces beyond the minimum
   data-home.
11. Task 6: replace fixture-only free-growth tests with data-mutation tests plus
   canonical-corpus readiness checks.
12. Task 9: repair G4/G5 as waist court — done for the GX vertical; multi-family
   producers arrive in GY.
13. Task 11: repair G8 blocker-specific auditing — done; G8 now fails closed
    when current-blocker search is unmeasured.
14. Final Task 12: rerun the GX vertical and persist the reducer-produced measured
   outcome (engine-agnostic; no DAG dependency — the DAG-route outcome run is a GY
   task).
15. Regenerate artifacts only after reducers, resolver, provenance, and validators
   are in place.
16. Run targeted validators, full Layer 3 validation, backend verification, and
   architecture guardrails.

Task 8 (G2 pipeline) and Task 10 (G6) are **moved to GY** as subordination of the
`scientist_policy_design` DAG and `scientist/agent` platform; they do not run in
GX. GX completes at the honest no-G2 blocker/abstention.

Horizontal rollout is forbidden before step 8 (provisional Task 12) produces a
pinned-route reducer result. If it cannot run, stop and fix the missing
producer/resolver/corpus input instead of widening the plan. GY may not start
before provisional Task 12 records an outcome.

Process gates:

- Each task closes in its own PR or clearly isolated commit range.
- No task closes with uncommitted generated artifacts or untracked fixtures.
- Slice-plan status changes happen only after the corresponding validator and
  artifact regeneration pass.
- Full Layer 3 targeted validation runs at each task closeout, not only the final
  closeout.
- Budget overrun or scope expansion requires a stop-and-review note and a revised
  minimal shippable set before more rollout work starts.

## Global Acceptance Bar

GX scope ends at the hardened vertical and the honest first outcome. Engine
subordination (the `scientist_policy_design` DAG, `scientist/agent`, the fabric
catalog wiring, the literature pipeline) is **out of GX scope** and lives in
`GY-engine-subordination.md`, which may not start until provisional Task 12
records an outcome.

The plan is not complete until all conditions hold:

- The baseline was clean or explicitly scoped before GX diagnostics were added.
- The minimal data-home exists and the pinned flow no longer depends on runtime
  default request helpers.
- At least one pinned-route run on canonical corpora produced a measured
  reducer-authored outcome: `grounded_limited`, `grounded_abstention`,
  `search_ceiling_repair_required`, or a typed blocker with exact missing refs.
- The provisional pinned-route run occurred before any GY subordination work, and
  the final run explains drift from the provisional run.
- `layer3_gx_reducer_integrity_report.json` recomputes all persisted positive
  statuses from dereferenced inputs and reports zero unexplained drift.
- Every positive persisted Layer 3 status carries reducer provenance and input
  hashes.
- Every positive persisted Layer 3 status passes producer-root-chain validation.
- Measurement roots for the pinned route and sampled rollout surfaces are
  machine-replayed and hash-compared.
- Legacy per-slice green validators have no GX authority unless the validation
  authority boundary marks the slice `gx_hardened`.
- Runtime literal lint has zero unapproved hits.
- No old fallback path remains after the replacement path exists; deletion is
  required for legacy construct mappings and scenario-family mappings.
- Search hits cannot become bindings without admission.
- Bindings cannot become grounded artifacts without materialization.
- Artifact refs cannot count without dereference.
- Closure statuses are reducer outputs only.
- Readiness manifests cannot override reducer outputs.
- Reducers do not accept inline producer-less inputs in production build/readiness
  paths.
- Production admission artifacts are conformance/admission derivations with
  measurement-root ancestry, not authored data rows.
- Free-growth mutation tests prove new data changes search without code changes.
- Production readiness search-health names canonical corpus path and snapshot
  hash, or reports `bounded_surrogate`.
- Blocker-specific recall uses canonical-corpus overlay injection and never counts
  injected rows as grounding.
- Downstream G4/G5/G8 cannot count phantom refs or seed-only health.
- G0 residual debts are closed or block GX closeout with owner and closeout
  condition.
- Published false governed artifacts have correction/retraction records.
- New statuses are registered in the vocabulary delta with composition rules.
- Issue-code-only conditions are not added to the status lattice.
- Human approval requirements cite the `deniskopylov` principal or a repo-owned
  replacement principal and have machine-checkable approval receipts.
- Layer 2 readiness is rerun after core mapping removal, with any migration
  blockers owned by GX.
- Full Layer 3 targeted validators are either pass or intentionally blocked with
  typed issue codes that match the reducer truth tables.

## Required Closeout Evidence

Before marking this plan completed, attach or regenerate:

- Baseline note with clean/scoped worktree evidence and pre-existing red checks.
- Minimal data-home artifacts for pinned request, concept/scope rows, and
  demand-pull request.
- GX runtime literal lint artifact.
- GX reducer integrity report.
- Positive status provenance inventory.
- Producer registry and producer-root-chain report.
- Measurement replay report.
- Persisted status recompute drift report.
- Independent audit sample with manual root tracing and physical measurement-root
  checks.
- Validation authority boundary report.
- Expected-red checks report for pre-provisional GX failures.
- Human approval receipts for allowlist/vocabulary/manual-audit exceptions.
- Status vocabulary delta.
- Correction/retraction log for false governed artifact claims.
- Universal search ledger schema/artifact examples for G1, G2, G3, and GL.
- Canonical corpus path/snapshot-hash report for production search-health.
- Canonical-corpus overlay injection report for blocker-specific recall.
- Reference resolver report with missing-ref negative controls.
- Data-mutation free-growth test report.
- G1/G2/G3/GL search-health reports with seed, pinned-case, and blocker-specific
  sections.
- G4/G5 dereference and waist-court reports.
- G6 actual tool-loop audit and demand-pull provenance report.
- G8 domain-vs-search-ceiling report with blocker-specific evidence.
- Provisional and final pinned-route outcome reports with reducer ids, input
  hashes, output hashes, producer roots, status, blockers, and next missing
  producer if blocked.
- `architecture/generated_artifacts.toml` and public/reference docs updates.

If any old fallback remains, the correct closeout is `blocked_legacy_fallback`,
not completed.

## Closeout Attempt - 2026-06-13

Closeout status: **blocked, not completed**.

GX-specific hardening evidence is green:

- `uv run python tools/quality/validation/check_policy_design_case_layer3_gx_hardening.py --repo-root . --write --output-format json` exited 0.
- GX validator summary: `status=pass`, `issue_count=0`,
  `expected_red_check_count=0`, `runtime_literal_issue_count=0`,
  `positive_status_count=0`, `measurement_replay_status=pass`,
  `producer_count=9`.
- `architecture/policy_design_case/layer3_gx_expected_red_checks.json` is
  `status=empty` with `final_task12_complete=true` and
  `provisional_task12_complete=true`.
- Final pinned route is an honest blocked outcome, not useful-design credit:
  `layer3_gx_final_pinned_route_outcome_report.json` has
  `status=blocked`, `outcome_kind=search_ceiling_repair_required`,
  `outcome_source=reduce_g5_conversion_outcome+reduce_g8_domain_vs_search_ceiling`,
  and `useful_design_credit=false`.
- `uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_gx_hardening.py tests/unit/runtime/quality/test_layer3_status_reducers.py tests/unit/runtime/quality/test_layer3_gx_data_home.py tests/unit/runtime/quality/test_required_reference_resolver.py -q`
  exited 0 with 45 tests passing.

Repository gates repaired or green during closeout:

- `uv run python tools/quality/validation/check_docs_accuracy.py --repo-root .`
  exited 0 with 0 violations across 468 checked files.
- `uv run polisyos-tools workspace tool-configs --check` exited 0.
- `uv run polisyos-tools architecture guardrails check` exited 0.
- `uv run polisyos-tools validation check-package-import-gates --fail-closed`
  exited 0 after updating `architecture/imports/dynamic.toml` for the moved
  `polisyos.scientist.policy_design` dynamic import site.
- `uv run python tools/quality/validation/check_substrate_drift.py --repo-root . --require-passing`
  exited 0 after registering the new Layer 3/GX unit tests in
  `architecture/production_quality/ci_tiers.toml`.
- Targeted ruff checks for the GX validator, docs accuracy gate, GX tests,
  reducer/resolver modules, `dynamic.toml`, and `ci_tiers.toml` exited 0.

Closeout blockers:

- Full Layer 3 targeted validation/test sweep remains red:
  `uv run pytest tests/unit/runtime/quality/test_layer3_*.py tests/repo_quality/tools/test_policy_design_case_layer3_*.py -q`
  exited 1 with 34 failures. The failures are concentrated in legacy readiness
  expectations for G1/G2/G3/G4/G5/G7 and unit expectations in G3/G5/G7 that
  still assume pre-GX pass semantics or future grounded breadth.
- Backend verification is not green. After fixing the HDS CI-tier registry issue,
  the fast backend pytest gate still fails. Reproduction:
  `uv run pytest -m 'not integration' --ignore=tests/unit/runtime/http -q -x`
  exits 1 at
  `tests/repo_quality/architecture/test_public_surface_snapshot.py::test_public_surface_snapshot_gate_matches_phase3a_baseline`
  because `architecture/baselines/structure_remediation/public_surface_pre_decomp.json`
  has public-surface snapshot drift. Inspection showed broad public-surface
  additions (21 modules and hundreds of objects), so this should be resolved as
  an explicit public-surface baseline decision, not silently folded into GX.

Closeout rule:

- Do not mark this plan `completed` until the broad Layer 3 readiness/test
  expectations are either migrated to the GX validation authority boundary or
  repaired to pass from reducer truth, and the backend public-surface snapshot
  gate is intentionally regenerated or otherwise brought green.
