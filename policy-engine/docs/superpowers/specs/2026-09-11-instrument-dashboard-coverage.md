# Dashboard coverage: measured execution, declared omissions

Date: 2026-09-11. Workstream: `dashboard-coverage-adequacy-below-the-unchanged-floor`.
Owner: `team-frontend`. Lane merge base: `cc74d6581`; branch:
`codex/instrument-honesty`. This decision precedes all source and test changes.

## Decision and acceptance

Keep `coverage-baseline.json` unchanged, including its 85.57% statement floor.
Exercise useful behavior in the named unexercised source, preserving its current
production contracts. A successful complete V8 run and independently reconciled
summary at or above every unchanged floor closes adequacy. This work does not
adjudicate historical regression ownership: it remains `not_established` because
the previous lane changed measurement inputs and no prior complete source map is
available for a like-for-like comparison. No hosted CI success is claimed.

Extend the existing ratchet so it distinguishes a measured rejection from an
unavailable or incomplete measurement. It must state its scope and limitations
even on success. Do not lower a floor, add tolerated deficit, exclude new source,
or add assertions whose purpose is merely to execute lines. A known limitation
does not become a pass merely because its prose was moved into this document.

## Owners composed and inspected evidence

The existing chain is `ci.yml::frontend-unit-coverage` and local
`tools/devx/workspace/ci_parity.py` → dashboard `package.json::test:coverage` →
`vitest.config.ts` with V8 provider →
`_build/apps/runtime-dashboard/coverage/coverage-summary.json` →
`scripts/check-coverage-ratchet.mjs` → process exit and terminal output. CI-parity
is a discovered caller, not a command authorized for this lane. The package script
already stops before ratchet execution when Vitest fails. The direct ratchet is
an artifact consumer and cannot claim that the suite producing an old report ran.

At the pinned base the ratchet reads only `summary.total[metric].pct`, compares
it to the baseline/absolute maximum, and exits 1 for both a missing report and a
measured shortfall. It does not reconcile per-file records, their aggregate
counts, percentages, or their file set against the configured source scope.
Missing-data failure does not print a complete-versus-incomplete verdict. A
self-consistent report omitting an included file can therefore claim a green
ratio. This is the deciding negative for the instrument repair.

The unchanged source scope is the explicit include/exclude globs in
`vitest.config.ts`; it is narrower than all dashboard source. The four metrics
measure execution counts for instrumented statements, lines, functions and
branches. They do not measure assertion quality, semantic correctness, browser
journeys outside the selected suites, production invocation, source-content
freshness of a supplied report, backend behavior, or hosted CI completion.

The supplied prior 7,047 / 8,277 statement observation is a finding pointer, not
a new measurement by this lane. The current source and actual new full report
decide the final ratio. Complete output is retained under the ignored
`docs/superpowers/journals/instruments/coverage/raw/`; the completion journal
cites output digests and tracked files as `path@sha` rather than copying source.

## Behavioral source selection and production invocation boundary

An AST census walked every `.ts` and `.tsx` file under
`apps/runtime-dashboard/src` on this branch before implementation (1,110 files,
including test sources; TypeScript `createSourceFile` and `forEachChild`, not a
`def` or identifier-count grep). Identifier contexts show these bindings:

* `useRunScenarios` is called by
  `AppShell.tsx::CounterfactualShellRail` and
  `features/whatif/ScenarioWorkbench.tsx::ScenarioWorkbench`. Existing shell and
  run-detail surface tests mock its entire module, bypassing request construction,
  schema admission, query identity, enabled guards, and error projection.
* `GlobalShortcuts`, `ReproduceRunButton`, and the exported
  `useScenarioCapabilities` have declarations but no production identifier
  reference in that complete file-type denominator. Their current state is
  `bridge_missing`; tests do not promote it to a wired product capability.
  This census does not resolve computed imports or external application callers.

The lane will not wire dormant controls into the shell or run actions to improve
a number. Those are product decisions with keyboard, authorization and execution
consequences. Existing component contracts still deserve meaningful regression
tests: their test-only invocation will be recorded openly, and the coverage
instrument will explicitly say that execution coverage does not prove production
reachability. Incidental wiring findings route to `team-frontend`'s component
integration backlog in the root completion journal; no debt register is edited.

The behavioral witnesses are:

1. `GlobalShortcuts.test.tsx`: real keyboard events drive navigation, preference
   changes, the help overlay, editable-field suppression, and list focus bounded
   at first/last items. Real router, keyboard registry, theme/density providers
   and preferences compose; assert location, DOM, focus and persisted preference
   changes rather than mocked callback counts. Removing shortcut registration
   must break a navigation/help assertion. These tests protect the published
   component contract; they do not prove the app currently mounts it.
2. `ReproduceRunButton.test.tsx`: cancellation performs no reproduction;
   confirmation passes source identity and parameters, prevents duplicate
   submission while pending, projects returned run identity, and exposes a
   rejection with a recoverable dismissal. A deferred callback is the component's
   explicit external effect boundary, not a replacement for internal code.
   Removing confirmation invocation must leave the observable terminal state
   absent. No claim about an actual backend reproduction endpoint is made.
3. `useScenarioCapabilities.test.tsx`: use the real query hooks, query client,
   parameter conversion and validators against an HTTP boundary. Assert returned
   admitted data, error states for unavailable/malformed responses, disabled
   queries, and scenario/time-aware cache identities. Exercise `useRunScenarios`
   through the same exported hook the production shell/workbench calls. Removing
   its temporal/scenario parameters must break the request/caching witness.

## Ratchet mechanism and non-test callers, named before construction

Reuse `check-coverage-ratchet.mjs`; no new parallel coverage gate. Move its exact
existing include/exclude arrays to `scripts/coverage-scope.json`, imported by
`vitest.config.ts` and read by the ratchet. This is shared configuration, not an
extra authority producer. All current globs remain byte-for-byte identical.
Node 22's filesystem glob expansion derives the expected actual source file set
from those globs. No directory-wide test run is needed for that read-only census.

The ratchet admits a report only after checking required finite integer counts,
covered ≤ total, the provider's truncated percentage arithmetic, per-file sums
against reported totals, and equality between measured file records and the
current configured source set. Missing, malformed, duplicated/aliased or extra
records produce `UNRUN`, exit 2, with named omissions and no complete verdict.
Well-formed complete reports below a floor produce `FAILED`, exit 1. A complete
report meeting all unchanged floors produces `passed`, exit 0. Existing configured
tolerance is validated and disclosed; this lane runs at its unchanged zero value.
Per-file zero-population metrics admit the actual reporter's 0% and 100% forms
as specified in the post-wave refinement below; they cannot conceal an absent
file or supply execution observations. An observation-free aggregate is UNRUN.
A missing or malformed baseline cannot become a metric failure.

On every invocation print the measured scope and a sentence of this form:
`Not measured: assertion quality, production invocation, source-content freshness
of this report, suites not executed by its producer, code outside the configured
coverage globs, backend behavior, or hosted CI.` Also print the exact globs; a
reader must not confuse a current file-set reconciliation with source-content
provenance. On incomplete input print `Coverage ratchet UNRUN: no complete verdict`
and name the unmeasured file/metric/invalid artifact. A valid subfloor is a
measurement, not UNRUN. The negative harness must distinguish both.

The instrument's existing non-test runnable terminus remains
`package.json::test:coverage`, consumed by `ci.yml::frontend-unit-coverage` and
the workspace driver. It should not gain a Python `polisyos-tools` wrapper:
that would duplicate a frontend package-owned, already discoverable command and
would needlessly add a Python prerequisite to the Node artifact checker.
`coverage-scope.json` is consumed directly by both existing production owners.
New tests use the standard Vitest project discovery and explicit local filenames.

## Falsifiers, predicate provenance and bounded limitations

| Property | Predicate / provenance | Deciding negative |
| --- | --- | --- |
| A green ratio covers the declared source-file set | File set recomputed from live globs and filesystem; report records independently reconciled | Remove an included file's record, rebuild all totals as 100%, retain the source file: exit 2 names the missing file, never passes. |
| Aggregate metrics describe their records | Counts and provider percentage arithmetic recomputed | Corrupt a count or percentage while retaining a superficially green total: exit 2 names the inconsistency. |
| Missing report is distinguishable from bad coverage | Local artifact read result recomputed | No summary or malformed JSON: exit 2/UNRUN. A valid 84% report: exit 1/FAILED. |
| Unchanged adequacy floor is met | Full suite produces counts; report arithmetic independently reconciled | The current complete suite remains below 85.57%: row stays open regardless of test count. |
| Behavioral tests assert substance | Observable router/DOM/query state recomputed | Remove the real callback/registration/query-scope operation with markers retained; named test fails for that operation. |
| Coverage does not prove reachability or freshness | `not_established` by this instrument | A complete high-coverage fixture still prints both named omissions rather than claiming either property. |

P38 distinction: passing percentages are a proxy for semantic adequacy. A test
that executes every statement without an assertion has full coverage and proves
no behavior. The instrument must declare that bounded limitation; behavioral
witnesses supply separate evidence. File-set reconciliation likewise does not
establish source hash or producer execution provenance. This lane makes that
omission explicit instead of inventing an attestation that a fixture can forge.

## Seams preserved, sequencing and verification

No runtime API schema, component public props, router integration, feature flag,
baseline value, coverage source membership, lockfile, workflow, pyproject,
lefthook or architecture owner is changed by this workstream. If a later finding
requires one of the shared files, root alone serializes its change and records
the effects on every lane. Extracting scope affects the dashboard producer and
consumer together; CI still invokes the same package script and retains the same
thresholds. Other lanes' products are outside the measurement claim.

After this document is committed and read back from the attached branch, write
the ratchet negative tests and observe their intended failures before changing
the checker. Add the meaningful component/hook witnesses and run focused
removal probes against temporary saved source, restoring exact bytes before
closeout. Every deciding invocation is a single gate command with its real exit
status and complete output retained. No shell `echo` masks the gate's status.

Targeted iteration and final runner name explicitly:
`scripts/check-coverage-ratchet.test.ts`,
`src/app/layout/GlobalShortcuts.test.tsx`,
`src/features/runs/components/ReproduceRunButton.test.tsx`, and
`src/api/hooks/useScenarioCapabilities.test.tsx`, with exact test names recorded
after collection through Vitest/AST. Root owns the integrated review/freeze. Only
then run the single authorized complete dashboard `test:coverage` suite with its
complete output under ignored `raw/`, followed by a direct ratchet artifact
readback when useful. That full coverage suite is the user's sole broad-suite
exception. No backend-wide, directory-wide, or CI-parity runs are authorized.

## Pattern pass and handoff

Existing patterns: P03/P04 (output cannot distinguish measurement absence),
P35 (summary denominator not reconciled), P37/P38 (percent field trusted as a
complete-measurement predicate), P01/P02 (dormant components are not invocation
evidence), P29/P33 (line execution alone is not a behavioral witness), P41
(historical ownership remains unestablished). Target pattern: one existing
producer/consumer chain, generic current-scope reconciliation, explicit omission
output, real negative cases, and separate useful behavior evidence.

The measurement chain has `verification_missing` and `surface_missing` for
unmeasured-input semantics before repair. Dormant UI artifacts remain
`bridge_missing`, explicitly routed rather than hidden or gratuitously wired.
The root completion journal records the actual full-suite ratio/verdict, the
exact printed omission sentence, negative receipts, explicit caller limitations,
and incidental findings' named destinations. A full coverage pass closes this
row only; it does not make dormant components production-wired or certify CI.

## Post-wave refinement: zero-population reporter representation

The complete final producer wave exits 0 (643.40 seconds), with 7,154 / 8,277
statements = 86.43%, while the ratchet exits UNRUN/2 on a present source file's
zero-population metric. This is a NEW producer-representation class: the initial
consumer assumed that every 0/0 metric must print 100. It is not a measured
floor failure. The existing successful suite/report remain evidence for their
unchanged source; no earlier incomplete report supplies this ratio.

The installed owners explain both legitimate forms. `istanbul-lib-coverage`
3.2.2 calculates 100 for 0/0. `istanbul-lib-report` 3.0.1 caches a report node's
summary; `istanbul-reports` 3.2.0 HTML reporting changes a lines-empty child's
cached percentages to 0. `@vitest/coverage-v8` 4.1.5 executes the configured
text, HTML, JSON-summary and lcov reporters against that context in order.
Consequently the actual JSON artifact legitimately contains both 0/0,pct=0 and
0/0,pct=100. The complete report census, installed owner source/hash evidence
and failed ratchet output are retained in the coverage raw receipts.

Extend only the existing ratchet and its existing test file. For a per-file
metric, `total == 0` and `covered == 0` admit precisely those two reporter
representations. Every nonzero population still requires recomputed truncated
percentage equality. Preserve finite/integer/count bounds, exact current source
membership and aggregate count reconciliation. An aggregate metric with no
observations is explicitly UNRUN, rather than manufacturing an adequacy pass
from a vacuous percentage. The CLI names that zero-population records carry no
execution observations; accepting their representation does not certify source
content, producer execution or behavior.

Falsifiers: remove a legitimate zero-population source record while retaining
its source file and unchanged totals; use nonzero covered with zero total;
forge a nonzero percentage; supply an arbitrary empty percentage such as 50;
or supply an all-empty aggregate. Each must remain UNRUN. Both admitted 0/0
encodings must pass in a complete mixed report without changing its numerator,
denominator or unchanged floor. Write and observe the new intended red before
the consumer edit; run every existing and new ratchet test by explicit name,
then admit the retained actual V8 report through the corrected registered
consumer. A report-content corruption negative must still fail.

Production caller remains dashboard `package.json::test:coverage` and its
existing CI/workspace callers. This is a consumer extension, not a new module,
CLI, fixture producer, or authority owner. The two mechanism paths are
`apps/runtime-dashboard/scripts/check-coverage-ratchet.mjs` and its existing
`.test.ts` file. No included product source, baseline, tolerance, coverage glob,
lockfile, shared Python/architecture configuration or generated artifact changes.
Every other lane therefore retains the same provision and source contracts;
the only changed consumer decision is admission of the actual empty-file
representation and explicit refusal of observation-free aggregate metrics.

Before reusing the successful full report, enumerate its complete file set and
the live include/exclude expansion and prove both mechanism paths intersect the
measured source denominator at zero. Preserve the full source-content digest
and original report bytes across the edit. That evidence justifies a targeted
ratchet replay instead of another full coverage wave. P38 diagnoses the wrong
representation predicate; P29/P33 require actual consumer negatives; P35 requires
the complete denominator; P04 keeps absence of aggregate observations distinct
from a measured shortfall. Acceptance is a correct complete ratchet verdict
with all unchanged metric floors and explicit omissions still printed.
