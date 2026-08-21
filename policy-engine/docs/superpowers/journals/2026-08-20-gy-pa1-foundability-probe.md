# GY-PA1 Foundability Probe Journal

Date: 2026-08-20

Branch: `codex/gy-pa1-foundability-probe`

Dedicated worktree:
`/Users/deniskopylov/polisyos/.worktrees/gy-pa1-foundability-probe`

Entry pin: `c054752637a9589fb99808bcdac5a97ae83f2906`. The branch was attached and
the worktree was clean before measurement and before the two authorized documentation writes.
No source, test, tool, governed artifact, or revision-line byte moved. `[P37: recomputed]`

## Census and anchor disposition

At the entry pin, the tracked denominator is 9,901 files, 9,879 under `policy-engine`, including
5,566 Python files and 2,560 Python files under `policy-engine/src`. A tracked-file byte scanner and
`git grep` independently agreed on the named populations; Python AST enumeration independently
classified constructor and executable-call populations. `[P35: denominator reconciled]`

| Handed anchor | Typed finding | Complete-set evidence |
| --- | --- | --- |
| `ValueOuterSet` definition at `value_outer_set.py:154`, `compare` at `:408` | `confirmed` | Direct source readback at those lines. |
| Empty Foundry placeholder is the only source construction | `refuted` | AST: 2 direct calls plus 27 `interval_box` calls; 6 factory calls are in `src`. The direct source call at `foundry/contracts/state.py:295` is empty, but `data_state_substrate.py:1143` and four `skg_query.py` calls construct real content; `generation_cycle.py:4411` is a further real-content helper. Textual `git grep` and `rg` each returned 30 constructor-like rows: those 29 calls plus the class definition. |
| Every source `.compare(` call is another class; none is `ValueOuterSet.compare` | `partly_refuted; core zero confirmed` | Both textual scanners found 7 rows. AST found 5 executable calls, all schema-evolution calls. `MethodSandbox.compare` and `evolution.compare` at the class usage example are docstrings, not call sites. No executable source call targets `ValueOuterSet.compare`. |

## Five typed measurements

1. **Real-content `ValueOuterSet`: `implemented` generally; `producer_missing` in live N8.**
   `data_state_substrate._household_payload` derives three coordinates per non-empty household row,
   builds numeric lower/upper tuples, creates a certified interval box, and serializes its JSON in
   the returned payload (`data_state_substrate.py:1039-1180`). Four academic SKG lowering paths
   also construct interval boxes (`skg_query.py:1879,1970,2032,2252`). The empty Foundry default at
   `state.py:294-316` is therefore not the only producer. In contrast, N8's furthest owner-resolved
   live branch ends at `treatment_assignment_not_owner_derived`
   (`generation_cycle.py:1813-1830`); its Foundry-result constructor has only a definition and one
   test use, and all four `ValueGateReceipt(...)`
   constructors are tests/tools, not production source.

2. **`ValueOuterSet.compare`: `consumer_missing` in production, executable in tests.** The full
   source AST population has zero calls to that method. The focused contract witnesses construct
   non-empty interval boxes and exercise `dominates`, `incomparable`, and forced-timeout `unknown`
   (`test_value_outer_set.py:334-353`). Thus the method is not idle because no comparable content
   exists; it lacks a runtime consumer.

3. **N8 live value schedule / ranked recommendation: `producer_missing` plus
   `implemented_but_not_orchestrated` placeholders.** `generation_cycle.py` contains zero
   `value_schedule`, `AuthorizedValueSchedule`, `NormativeDecisionRequest`, ranked-recommendation,
   or participation-requirement references. Across the tracked tree,
   `build_authorized_value_schedule(` occurs in one source definition, one readiness-validator
   call, and two documents; it has no production source caller. `build_pareto_archive` accepts any
   non-empty ref not containing `shadow`/`scenario` (`value_choice_provenance.py:443-451`), while
   the S7 check trusts a supplied decision-class string and boolean (`:680-692`). The PDC consumer
   blocks a declared or absent ranking posture, but its attempted-ranking predicate is only
   `expected_welfare_optimization | value_gap` (`layer2_design_search.py:3495-3503`), not a live
   ranked output. `NormativeDecisionRequest` appears in exactly three documents and no code.

4. **`participation_requirement`: `implemented`, not declarative.** Both complete-tree scanners
   found the same 75 tracked files. The live chain is contract/compiler at
   `participation_requirement/__init__.py:166-565`, deterministic persistence at `:597-615`,
   evaluation at `:618`, claim-ledger bridge at `claim_decomposition.py:400-426`, producer-pipeline
   consumption/emission at `producer_pipeline.py:724-764,2182-2210`, and projection at
   `projection_semantics.py:3335-3414`. Its authority boundary explicitly denies participation,
   claim-support, closeout, and projection authority
   (`participation_requirement/__init__.py:115-122`).

5. **PA1 negatives:**

   - silent equal-weight / historical-prior / proxy-as-priority: `writable_but_placeholder_only`;
     real numeric social-weight manifests exist, but no live PA1/N8 authority producer resolves
     them, and `AuthorizedValueSchedule` carries refs rather than the aggregation payload;
   - legal-competence / wrong decision-rights role → `blocked`:
     `writable_but_placeholder_only`; the nearest test rejects a caller-declared wrong class with
     an exception (`test_design_axes_value_choice_provenance.py:360-397`), not a resolved
     competence artifact and typed blocked result;
   - no authorized schedule → frontier + typed `NormativeDecisionRequest`:
     `not_writable_or_exercisable`; the lower archive guard is executable and green
     (`test_design_axes_value_choice_provenance.py:232-251`), but the required request type,
     producer, persisted artifact, projection, and live ranked emitter do not exist.

## Execution receipt

Seven narrow existing witnesses ran under system Python because this worktree has no `.venv`.
Six passed: real interval construction, comparison, two participation witnesses, the archive
no-schedule guard, and the S7 decision-class guard. The N8 selection/acquisition node failed before
its asserted selected-method waypoint because this dedicated worktree has no `production_data`;
the observed value status was still `value_blocked`. This is an environment non-receipt, not the
basis for the static missing-producer finding. Elapsed time was 33.7 seconds. The complete Python
AST census took 46.5 seconds. No run crossed 60 seconds, so no contention regime was recorded.
Rounds remain `0 / 2`.

## Disposition and ownership

**GY-PA1 disposition: `producer_missing`.** This is not `bridge_missing`: the generic
`ValueOuterSet` carrier and participation chain are real, but the exact prerequisite N8 producer
does not emit a live `ValueGateReceipt`/certified set, and the S8 schedule factory is a
caller-declared contract helper rather than a resolved authority producer. Nor is the whole value
layer `absent/unallocated`: owners and substantial numerical substrate are present.

Foundability requires all of the following:

- an external rollout institution must sign an owner-derived assignment, or the knowledge/
  grounding producer must emit a certified SKG identity bridge; GY-N7's
  `runtime.quality.acquisition_planner` owns typed admission, receipt, and same-cycle re-entry, not
  the external institutional act;
- GY-N8's `runtime.quality.generation_cycle` value lane must dispatch the estimator and emit/persist
  a content-bound `ValueGateReceipt` with a real `ValueOuterSet`;
- GY-PA1's `runtime.quality` S8 value-authority lane must resolve/content-bind mandate,
  decision-rights, participation, dissent, TTL, and the real social-weight schedule; emit the
  authorization record or typed decision request; and gate an actual frontier/ranked consumer.

Only then can all three negatives be behavioral end-to-end witnesses. PA1 must not build or claim
the missing N7/N8 value producer while adding the authorization record. Relevant failure classes:
`P01`, `P02`, `P05`, `P10`, `P12`, `P15`, `P32`, `P35`, `P37`, and `P38`.
