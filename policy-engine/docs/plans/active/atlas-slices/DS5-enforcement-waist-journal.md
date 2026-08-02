# DS5 Enforcement Waist Journal

## DS5-C01 — rejected mechanism retained as history

- Commit `b67084dd6` built an open-estate value-flow analyzer. Three independent
  reviews found distinct bypass classes. Architect ruling `636645bec` rejected
  that mechanism as an optimistic completeness envelope and re-cut the work as
  C01a/C01b/C01c.
- C01a is a forward removal commit. The rejected commit remains in append-only
  history as the honest record; no C01 or C01a receipt claims that arbitrary
  TypeScript value flow is completely analyzed.
- The retained claim is narrower: TypeScript enforces nominal branded slots;
  local syntax checks govern the escape hatches in C01b; issuers govern runtime
  novelty in C01c.

## DS5-C10 — deferred owner integrate contract

- **Disposition:** deferred on 2026-08-02; this downstream gap does not block
  C01-C09 or C11 onward.
- **Typed debt:** `g4-complete-audience-projection-contract` records
  `team-runtime-quality` as owner, five incomplete capability states, the exact
  eight-field projection contract, EXPERT `mode.analyst` authorization,
  provenance/hash/time/novelty requirements, and the executable owner-side
  closure signal.
- **Owner evidence:** the current G4 contract remains `projection_only`, route
  unregistered, and `out_of_scope_reference_only`; DS5 does not route or
  reclassify the raw owner artifact.
- **Register receipt:** commit `24e66b44c` used the byte-preserving supplemental
  writer and report writer; the live checker returned 261 roots, 14
  supplemental findings, 23 seeded negatives, and 8 censuses.

## DS5-C01a — authority-sink census and brand/debt boundary

### Entry and recovery receipts

- Entry HEAD was `24e66b44c` on
  `codex/atlas-ds5-enforcement-waist`. `git status -sb` first exposed a detached
  worktree; `git checkout codex/atlas-ds5-enforcement-waist` attached the
  already-equal branch without changing the five dirty reduction files.
- The workspace package links were installed before scanner evidence was used.
  The bounded TypeScript program contains 610 production files: 574 dashboard
  and 36 Atlas UI.
- The reduction delta over the five retained-core scanner/checker/test files is
  exactly 563 insertions / 2,828 deletions. The points-to/heap/CFG/HOF engine
  and machinery-only witnesses are absent; exact generated provenance, the
  status-inventory bridge, declaration-derived prop census, and opt-in compiler
  diagnostics remain.

### Red-first receipts

- The named authority-census battery was written before its registry APIs.
  Its first run produced four missing-API errors; the structural lookalike was
  rejected by the compiler as `TS2741`, proving the private brand was already
  unforgeable and correcting an initial test expectation of `TS2322`.
- After the live scanner returned 163 direct Badge sites and 19 prop groups,
  the focused six-test run remained red only because all 39 governed debt rows
  were absent: `test_every_authority_presentation_prop_is_branded_or_typed_debt`
  reported 39 `finding_id` drifts, and its corruption test could not select an
  unwritten row. The run was 6 tests in 345.530 seconds under concurrent scanner
  load.
- A later 82-test cluster run was 81/82 green and exposed one stale pre-C01a
  expected-ID assertion. The delta test passed 1/1 in 41.071 seconds after that
  assertion included the 39 governed authority descriptors.

### Finite census and typed-debt receipts

- Direct `Badge`: 163 sites / 52 files = 2 private-issued branded sites, 58
  authority-bearing sites in 27 typed debt groups, 103 benign sites in five
  explicit classes, and 0 unclassified. Benign classes are 13
  interaction/editor, 20 transport/runtime health, 24 workflow/lifecycle
  display without terminality inference, 21 layout/counts, and 25 opaque
  metadata/taxonomy.
- Authority props: 19 declaration groups / 35 uses = 2 branded/6 uses, 12 typed
  debt/21 uses, and 5 benign/8 uses. The full Badge partition is content-bound
  by `sha256:28e6c934ceb073b29a122f891424f75ae3f320353fc0ad65f59a046dffca79a2`;
  the prop partition is content-bound by
  `sha256:0b012a06e76027af5dd0d592c195d2ab7d55e1704da75a346bbfb69f82123410`.
- Each of the 39 new `authority_presentation_debt` rows carries owner slice,
  capability states, executable closure signal, exact 2026-08-02 decision date,
  declaration receipt, consumer count, and content-bound consumer sites.
  Missing rows, owner/state/closure drift, fingerprint drift, unclassified new
  Badge sites, authority-to-benign reclassification, duplicate IDs, old-row
  restamps, and new-row backdates are executable negative witnesses.

### Governed writer and content-binding receipts

- Before the first DS19 refresh, the diff from `b67084dd6` to `24e66b44c`
  changed only one semantic register item: supplemental findings 13 to 14 by
  adding `g4-complete-audience-projection-contract`; all root dispositions,
  seeded negatives, and eight census rows were unchanged. The resulting
  register hash was
  `sha256:cbf777376907f661b3eb6f2e56d5d02fdec0c81019187b73c617c3f871cd1227`,
  and the status-inventory corruption battery passed after that surgical
  receipt refresh.
- C01a's surgical writer then added exactly 39 rows, taking supplemental
  findings from 14 to 53. Its final second run was byte-identical at
  `sha256:7b09165e80942669c2ab432e3f09184275b6399a8de54a5a04a7ae4d3b941fc8`.
  Only `sources.ds19.sha256` was surgically refreshed in the status inventory.
- One provisional writer invocation stopped before writing because its
  partition digest used scanner locale order rather than the checker's
  canonical path/line/hash order. It is a valid red receipt, not a gate receipt;
  the measured canonical digest above replaced it.

### Final gates and review

- Fresh unit gates ran in three parallel read-only lanes: enforcement 6/6 in
  275.171 seconds, status inventory 38/38 in 346.609 seconds, and disposition
  register 38/38 in 263.829 seconds—82/82 total. The single stale assertion's
  post-fix delta test was separately green 1/1 in 41.071 seconds.
- Post-format governed checkers and corruption batteries are green:
  enforcement in 125.356 seconds (`36 / 163 / 19 / 47 / 15 / 0`), status
  retirement in 91.610 seconds (`47 / 15 / 55 / 0 / 3`), and disposition in
  152.446 seconds (261 roots, 53 findings, 23 negatives, 8 censuses). This is
  the final receipt for the status inventory's refreshed DS19 binding.
- Dashboard production build/typecheck passed in 120.515 seconds with 3,885
  modules, 108 PWA precache entries, post-build security, and Atlas Tailwind;
  ESLint passed in 63.586 seconds; both architecture engines passed across
  1,019 modules / 4,150 dependencies in 55.610 seconds; package-wired
  `lint:enforcement` passed in 191.475 seconds.
- Atlas UI typecheck passed in 30.040 seconds, ESLint in 40.816 seconds,
  architecture across 36 sources in 5.184 seconds, and Vitest 18/18 files / 86/86
  tests in 39.419 seconds.
- Node syntax, Python compilation, JSON parsing, and `git diff --check` passed.
  Scoped Ruff `E,F,I,B,N` passed with the exact inherited `E501`/`F841` classes
  excluded; exact-parent isolation reproduced the same two F841 identities
  (`baseline_files`, `ds1_by_id`). Prettier now passes the changed scanner and
  type witness; exact-parent isolation reproduces the remaining four document /
  governed-JSON formatting identities, so the zero-new set is exact and no
  surgical JSON was reserialized.
- The first workspace-link command used unavailable `readlink` and is a
  non-receipt. Its clean rerun resolved both dashboard `@polisyos/atlas-ui` and
  `@polisyos/runtime-api-client` links to this worktree's package directories.
- Independent code review: GO after one bounded fix round. Initial result was
  0 Critical / 1 Important / 0 Minor for stale reduction counts; the counts
  were remeasured and corrected, and delta-only re-review returned 0 / 0 / 0.

### Scope and residual claim

- Current measured scope is 14 paths under cap 15. There is no generated-client
  regeneration, backend write, engine-internal write, C02 work, or C10 build.
- C01a claims only a finite current-estate census, nominal branded-slot compiler
  enforcement, content-bound classification, and typed owner debt for every
  unbranded measured sink. It does not claim semantic discovery or complete
  value-flow detection for arbitrary future TypeScript.
