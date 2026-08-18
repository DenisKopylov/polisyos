# Atlas Honesty-Comprehension Protocol

Freshness: 2026-08-11
Instrument owner: `team-frontend` / DS6
Research-content owner: `INT-R3`
Contract: `apps/runtime-dashboard/src/test/evidence/atlasHonestyComprehensionProtocol.ts`
Storage convention: DS6-C07 / `polisyos.core.artifacts.ArtifactStore`

## Purpose and authority

This is the contract-only seed for the recurring reviewer procedure required by
the Atlas master plan. It asks two questions: “Find the weakest link.” and
“Find the active blockers.” The answers remain owned by the existing runtime
producers: `_project_depth_n` maps `terminal.blocking_obligations` to
`domain_runs.<domain>.weakest_links`, while `_closeout_truth` supplies
`PolicyDesignCaseProjection.closeout_truth.blockers`. Those bindings carry
`predicate_provenance=not_established` because C12 does not behaviorally verify
the Python producers. C12 measures whether a reviewer can locate the answers
and does not implement another weakest-link or blocker algorithm.

Every response preserves three planes required by the Stage-0 research input:
external execution, evidence status, and the PolicyOS reaction. Mixing those
planes would let an operator mistake an institution's act for evidence arrival
or for PolicyOS authority.

The protocol is authoritative only for a descriptive honesty-comprehension
observation. It is never a benchmark pass, review-effectiveness policy,
maturity decision, publication decision, or runtime/policy authority. Its
interpretation is always `descriptive_only`, with `blocking_permitted=false`,
`grants_stable=false`, and `stable_bar_effect=not_established`.

## Owners and cadence

- DS6 / `team-frontend` owns the instrument envelope and the seed procedure.
- INT-R3 owns behavioral content, correctness semantics, thresholds, and any
  later benchmark claim.
- DS6-C11 owns later measurement instrumentation.
- Core `ArtifactStore` owns persistence mechanics.

The collection cadence is quarterly, before the first stable claim for an
interactive authority surface, and after an authority-surface semantic or
instrument-profile change. This is scheduling only. It is not evidence
freshness, validity, TTL, retention, or a promotion threshold; C07's distinct
observation/collection/verification and 365-day retention roles remain intact.

## Sampling

The declared method is preregistered risk-stratified sampling. The procedure
declares risk strata, preregisters and freezes the frame before observation,
selects only subjects in that frozen frame, and records inclusions and
exclusions.

No sample-size floor, coverage percentage, representativeness claim, or frame
completeness is established. `frame_ref`, `preregistration_ref`, and
`sample_size` are currently null; completeness and its P37 predicate
provenance are `not_established`. Future frame refs must parse through C07's
canonical `ArtifactID` schema (`sha256:<64-lowercase-hex>`), but even a valid
identity leaves `sampling_completeness=not_established`. Presence of an
ArtifactID is not resolve-bind-verify evidence under P32.

## INT-R3 replacement seam

The outer schema and instrument profile have independent versions. The exact
seed ID/version is content-bound to its two tasks, producer/field bindings,
response planes, metrics, conditions, and null threshold rows. A changed seed
therefore requires a new identity/version rather than replaying altered content
under `ds6.honesty-comprehension.seed@1.0.0`. Other profile identities use
generic, uniqueness-checked arrays, so a researched behavioral profile can
replace the seed without changing the outer protocol envelope. Every task must
declare the producer and field for its expected answer with
`predicate_provenance=not_established`; a declaration cannot silently become a
new truth producer.

The seed reserves the six identities named by the INT-R3 task:

- `false_action`
- `false_pass`
- `missed_blocker`
- `unsafe_override`
- `time_to_correct`
- `confidence_vs_correctness`

It also reserves the named operating conditions `keyboard_only`,
`screen_reader`, `low_numeracy`, and `time_pressure`. Every replacement profile
must retain this six-metric/four-condition core; researched extra identities
may be added without changing the outer schema. Reservation or extension is
not measurement. Every condition and every metric threshold remains
`not_established`; each threshold has null comparator, value, unit, and source
reference. The schema has no current `established` branch. The alternate-profile
test proves only structural replaceability while retaining null thresholds—it
does not prove behavioral adequacy or research admission.

The `false_pass` token also exists in backend Policy Design Case adjudication.
That is a different measurement family and supplies neither INT-R3 semantics
nor a threshold. Likewise, ADR-0171 and
`src/polisyos/runtime/quality/human_review.py` already own review time,
override, dissent, no-delta, and separation-of-duty telemetry. C12 creates none
of those signals; C11 may later compose their existing report with this
distinct comprehension instrument.

## C07 storage boundary

C12 aliases the exact C07 storage object and denial prefix. It does not create
a second receipt, payload envelope, CAS, retention rule, or writer. The
protocol is suitable as strict rule-owned verification-payload `details` once
a legitimate generic reviewer evidence kind and producer exist.

C07's current closed kinds are automated browser, automated keyboard, and
manual assistive-technology evidence. Generic human comprehension is not
mislabelled `manual_at` merely to mint a receipt. No protocol result is
persisted in C12, and the local classifier does not claim that a C07 artifact
exists or has passed Core integrity verification.

## Observation interpretation

The focused consumer keeps five states distinct: missing, unknown, known zero,
incomparable (`no_admissible_ranking`), and recorded. Even a populated recorded
observation remains descriptive, nonblocking, and non-stable because INT-R3,
sample completeness, a producer, persistence, integrity verification, and a
runtime consumer are absent. It computes no synthetic success score.

The current capability label is `contract_only`. Missing links are
`producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`,
actual-evidence `verification_missing`, and `surface_missing`.

## Authority artifacts

- Atlas master DS6 deliverable and Rev-3.4 rider:
  `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:1023-1043`
- INT-R3 task and live-operator requirement:
  `docs/research/policy-operations-and-real-world-runtime-backlog.md:251-255,453-457`
- three-plane boundary:
  `docs/research/policy-operations/stage0/sources/pao-r1-original.md:793-798`
- external-to-runtime-verdict boundary:
  `docs/research/policy-operations/stage0/sources/ops-r15-original.md:1900-1907`
- C07 storage and evidence contract:
  `docs/reference/frontend/atlas-evidence-artifact.md`
- canonical Policy Design Case blocker producer:
  `src/polisyos/runtime/quality/projection_semantics.py:356-367,2843-2889`
- S9's downstream normalization boundary (not the general producer):
  `src/polisyos/runtime/quality/projection_semantics.py:2418-2425,2526-2561`
- advisory review-effectiveness owner:
  `docs/adr/0171-review-effectiveness-telemetry-advisory-first.md`

Focused non-browser verification:

```bash
cd apps/runtime-dashboard
corepack pnpm exec vitest run src/test/evidence/atlasHonestyComprehensionProtocol.test.ts --maxWorkers=2 --reporter=default
```
