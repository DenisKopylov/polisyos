# DS7 Task 4 RED Closure Basis

**Status:** frozen before the next RED review wave
**Controlling spec:**
`docs/superpowers/specs/2026-08-20-ds7-cycle-board-design.md`
**Execution plan:** `docs/superpowers/plans/2026-08-20-ds7-cycle-board.md`

## Review bucket

This document is the complete Task 4 RED property population. Reviewers receive
this bucket before reviewing a repaired seam:

- During RED, a finding against a property already listed here is convergence.
  Repair and re-review it; it consumes no mechanism round.
- A finding that the eventual projection identity, owner boundary, fact algebra,
  or production shape is wrong is a mechanism finding.
- A finding naming a property absent from this basis is a new class. It consumes
  one seam round and amends this basis once, with the amendment recorded.
- A negative that cannot be exercised because its smallest closing capability is
  absent is a bounded residual. State the missing capability, run the absence
  falsifier, and never call the property green.

The basis is split by independently rejectable seam. Task 4a defines facts;
Task 4b controls access and replay of those facts; Task 4c binds source loading
and declares the rendered-DOM boundary that later consumes them.

## 4a — composition and fact algebra (`0/2`)

| ID | Frozen property | Production mutation the RED must catch | Witness / initial state |
| --- | --- | --- | --- |
| `4A-FACT-01` | Every optional board value is a discriminated available/absent fact. `not_established`, `artifact_missing`, and `invalid_source` remain distinct; an absent branch has no `value`. | Defaulting an absence to `false`, `non_terminal`, producer `not_established`, zero, or an empty value. | Lifecycle and legacy REDs present. |
| `4A-TERM-02` | Lifecycle terminality comes only from an exact producer-signed `RunSummary.run_terminality` binding. Status text, novel status substrings, `started_at`, `finished_at`, duration, search terminal kind/distribution, blockers, and acquisition posture are the complete prohibited proxy classes. Search terminal and lifecycle terminal mutations are independent. | Adding any status/time/search fallback, accepting a mismatched run binding, or coupling search and lifecycle truth. | REDs present; independent `started_at`/duration changes and a signed mismatched-run negative must be added. |
| `4A-PROBLEM-03` | The raw owner validates and propagates the canonical `DesignProblem`; malformed provenance is `invalid_source`. Each composed N10 row then carries the exact available raw-owner problem. | Replacing the owner object with a shaped surrogate, dropping provenance, or failing to carry it into v2. | Raw adversarial/refusal REDs present; composed equality must be added. |
| `4A-OWNER-04` | Evidence class equals live canonical `_domain_evidence_witness` recomputation and ordered weakest links equal the canonical terminal blockers over the complete three-role N10 owner population. Corrupting class or order fails. | Copying a free label, client/server reclassification, sampling one role, sorting or dropping blockers. | Behavioral owner-recomputation RED present; independently equate recomputed keys, raw `domain_runs`, and `N10_ORDER`. |
| `4A-COHORT-05` | Rows are exactly the three N10 roles in owner order followed by all thirteen legacy fixtures in manifest order. `/runs/nl`, unbound jobs, and unknown future submissions add no row; the run list is never enumerated. Legacy runtime fields remain `artifact_missing`. | Inflating the denominator from shadow jobs, fabricating future rows, dropping/reordering fixtures, or deriving legacy runtime facts. | Behavioral RED present. |
| `4A-COVERAGE-06` | GAP5 is the full typed `absent/unallocated` coverage record with exact deficits, missing link, N12 owner route, execution state, known scope/count, unknown future scope, and `exhaustive=false`. Mutating global N13b evidence cannot change ordered row IDs, known count, or exhaustiveness. | Treating a global demonstration as membership, changing the 3+13 denominator, or claiming completeness. | Typed RED present; N13b enumeration/exhaustiveness comparison must be added. |
| `4A-MOVEMENT-07` | GAP6 is the full typed `absent/unallocated` movement record with GY-N13b/GY-N12 routes and honest-empty board/per-row movement. Changing global N13b status cannot mint movement. | Projecting global `typed_deeper_terminal` as per-row motion or simulating a closure. | Behavioral injected-signal RED present. |
| `4A-STRUCTURE-08` | Raising adjacent N13a observation/catalog counts cannot change evidence class, ordered weakest links, missing link, acquisition route/execution, movement, cohort membership, or coverage. | Laundering nearby row counts into structural support, membership, completeness, or motion. | Structural-field RED present; compare complete ordered row IDs and coverage alongside the N13b comparison. |
| `4A-ROUTE-09` | The complete owner costed route propagates through raw and composed packets: owner, gap identity, missing fields, strategy, producer, next action, cost, VOI, and rank. Missing cost/VOI/execution are typed absence, never zero or implied execution. | Hard-coding the fixture route, dropping economics, or treating a plan as execution. | Raw adversarial RED and partial composed RED present; composed full-field equality must be added. |
| `4A-SOURCES-10` | The composition manifest derives and enumerates its complete input population exactly once: five governed projection states, N13b control-plane evidence, the historical DS4 source, the historical availability source, and each exact-bound lifecycle lookup. Each retains availability, source/dependency identity, own `as_of` and freshness where its owner supplies them; `invalid_source` never downgrades to `artifact_missing`, and no aggregate currentness is minted. The historical 5/7/1 result remains independently parsed, environment-relative, and non-current. DS8/readiness absences expose no value. | Omitting/duplicating a source, remembering a smaller denominator, flattening time, relabeling an invalid producer, treating the DS3 measurement as current, or inventing DS8/readiness data. | State/denominator RED present; full population, per-source time, and no-value assertions must be completed. |
| `4A-DS4-11` | Realized DS4 disposition is derived from the complete historical owner table, raw-byte content-bound, arithmetically reconciled, and carried into v2 as historical—not current estate readiness. | Pinning `27/41/18/3`, reading the current 261-entry register as that denominator, dropping a family row, or omitting the result from the packet. | Parser/corruption RED present; composed carry assertion must be added. |

## 4b — access and replay (`0/2`)

| ID | Frozen property | Production mutation the RED must catch | Witness / initial state |
| --- | --- | --- | --- |
| `4B-ROUTE-01` | There is exactly one static Cycle Board GET before exactly one dynamic governed-projection sibling, with operation ID `get_depth_n_cycle_board_projection`. | Duplicate/parallel owner, deletion, reordered fall-through, or operation-ID drift. | Route-census RED present. |
| `4B-AUTH-02` | The static operation carries a direct executable `RUNS_REVIEW` + `TENANT_COLLECTION` dependency for `runtime.governed_projection.depth_n_cycle_board`. ANALYST/reviewer is admitted; VIEWER/runs.view is denied before service/query/replay work. | Marker-only auth, wrong permission/resource, handler-before-auth, or viewer admission. | RED present; denied-call cardinality must be explicit. |
| `4B-VERSION-03` | An unpinned authorized request executes the real strict composed-v2 path and discriminates `policyos.runtime.depth_n_cycle_board.v2`; it is never satisfied by a raw-only test double or raw-v1 fall-through. | Weakening the v2 DTO, installing the raw fake too early, or silently returning v1. | Harness ordering repair required. |
| `4B-RAW-04` | A complete raw-v1 tuple—`artifact_content_hash`, `projection_hash`, `source_dependency_hash`, and `source_as_of`—returns canonical JSON bytes from the same frozen raw observation, with one raw-owner read and no recomposition. | Dropping a legacy pin, comparing two timestamped observations, reserializing a v2 model, duplicate reads, or self-composition. | Frozen-observation RED present after ordering repair. |
| `4B-V2PIN-05` | A complete v2 tuple binds rule version, composition manifest, projection hash, and dependency hash; changing any source state/typed absence changes replay identity. | Accepting stale composition or omitting an absent source from identity. | Service RED present. |
| `4B-CONFLICT-06` | Wrong complete raw pins, untargeted pins, partial raw/v2 tuples, and mixed-generation tuples fail through the typed service conflict and authorized HTTP 409 translation. v1 and v2 are never reinterpreted. | Partial matching, cross-version laundering, uncaught service errors, or an untyped HTTP failure. | Service RED present; authorized HTTP wrong/partial/mixed conflict witnesses must be added. |

## 4c — loading and parity (`0/2`)

| ID | Frozen property | Production mutation the RED must catch | Witness / initial state |
| --- | --- | --- | --- |
| `4C-N13B-01` | The N13b loader reads the exact owner artifact and computes `source_content_hash` from its raw UTF-8 bytes. | A stale/constant hash, normalized/reformatted hashing, or a substituted file. | Raw-byte equality RED must be added. |
| `4C-N13B-02` | The loader admits only the artifact's declared schema, rule, and producer. A missing/unreadable artifact becomes `artifact_missing`; malformed JSON or substituted schema/rule/producer becomes `invalid_source`. Neither branch mints a global fact or fails the whole board. | Collapsing distinct absence states, trusting shape/status alone, or making an optional source fatal. | Validation/refusal REDs must be added. |
| `4C-N13B-03` | An admitted signal is explicitly control-plane evidence, authoritative only for global demonstration status and denied for per-row movement, row enumeration, and exhaustiveness. Its behavioral denials are owned by `4A-COVERAGE-06` and `4A-MOVEMENT-07`. | Labeling the frontier exhaustive or silently promoting it to row authority. | Manifest authority RED present. |
| `4C-DS8-04` | Missing DS8 binding is a capstone `not_established` fact with DS8 route and no value; legacy is `artifact_missing` with no value. | Inventing a link, defaulting an empty href, or treating fixture identity as a trace. | Availability/route RED present; capstone no-value assertion must be added. |
| `4C-DOM-05` | The real authorized page's complete raw semantic DOM equals `packetToVisibleCycleBoard(packet)`, and downloaded MACHINE bytes equal the server packet. Dropped/duplicate rows, defaulted absences, omitted sources, fabricated movement, localized raw values, or changed download bytes fail. | Any second client model or human/export divergence. | **Bounded residual: `semantic_test_missing`; not green.** See below. |

## Declared bounded residual: `4C-DOM-05`

The smallest closing capability is:

```text
CycleBoardPage + packetToVisibleCycleBoard + stable raw semantic DOM slots
+ MACHINE download trigger
```

That capability does not exist before the hero mechanism. On 2026-08-20 the
absence falsifier enumerated all tracked dashboard source TypeScript/TSX files
under `apps/runtime-dashboard/src` twice:

```text
git ls-files + rg denominator: 971 files
git ls-tree + rg denominator: 971 files
rg identifier/slot hits:      0 files
git grep identifier/slot hits: 0 files
```

The searched closure identifiers were `CycleBoardPage`,
`packetToVisibleCycleBoard`, `data-cycle-board-{raw,packet,row,source,gap}`,
and `downloadCycleBoard`. Therefore a server-only DOM test would be fabricated.
The residual stays `semantic_test_missing` until Task 9 can run this falsifier
against the real page: delete or duplicate a row, default an absent fact, omit
a source, fabricate movement, localize a raw slot, and alter downloaded bytes;
each mutation must fail the decoded-DOM/export comparison. DS16's rendered-DOM
decoder is the reuse precedent.

## Amendment protocol

This file's first commit is the freeze boundary. Before each seam review, the
review request cites the relevant IDs and states the bucket above. An on-basis
test-strengthening finding changes no round. A genuinely off-basis property is
added once with its reviewer finding and seam round recorded in the journal.
