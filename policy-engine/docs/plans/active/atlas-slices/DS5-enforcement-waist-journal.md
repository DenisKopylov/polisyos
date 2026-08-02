# DS5 Enforcement Waist Journal

## DS5-C01 — shared semantic engine and unauthorized-status-owner lint

### Entry receipt

- Base/HEAD: `d6b38294e4f59a79ac3e7f6bf6bb5db2ea923f3f` on
  `codex/atlas-ds5-enforcement-waist`; `git status --porcelain=v1` was empty.
- Workspace resolution: `apps/runtime-dashboard/node_modules/@polisyos/atlas-ui`
  and `runtime-api-client` both resolved to their workspace packages.
- Pre-positive live denominator:
  `rg --files packages/atlas-ui/src | rg '\.[jt]sx?$' | wc -l` returned exactly
  `36` production sources. The set contained no test, spec, or story source.
- Measured implementation set: seven product/governance files plus this journal;
  cap nine.

### Red-first receipt

Command:

```text
python3 -m unittest architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_package_namespace_alias_later_assignment_jsx_spread_revival_fails
```

Receipt: expected exit `1`, one test run, one assertion failure in `2.7 s`.
The scanner executed successfully, but
`('packages/atlas-ui/src/index.ts', 'PackageDecisionStatus') not found in set()`.
This is the intended missing-feature red: namespace import, wrapper, object
property, array carrier, later assignment, coercion, and JSX spread reached a
real `AuthorityBadge` fixture while generated-owner marker bytes and a
responsive interaction-state control remained present.

### Green and gate receipts

- Focused Python battery:
  `python3 -m unittest architecture.atlas_surfaces.test_atlas_enforcement architecture.atlas_surfaces.test_status_retirement_inventory`
  — PASS, 40/40 tests in `84.666 s`.
- DS4 governed checker:
  `python3 architecture/atlas_surfaces/check_status_retirement_inventory.py --check --corruption-probes`
  — PASS; corruption probes PASS; 47 DS1 rows, 15 current authored statuses,
  55 semantic exemptions, 0 retirement debt, 3 waist debts.
- Shared enforcement checker:
  `python3 architecture/atlas_surfaces/check_atlas_enforcement.py --check --corruption-probes`
  — PASS; corruption probes PASS; 36 Atlas UI production sources, 47 DS1
  rows, 15 current authored statuses, 0 unauthorized owners, 0 unauthorized
  sinks.
- Dashboard wiring: `corepack pnpm --dir apps/runtime-dashboard run lint:enforcement`
  — PASS with the same `36 / 47 / 15 / 0 / 0` receipt.
- Disposition register:
  `python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --verify-baseline-source-bytes --corruption-probes`
  — PASS; 261 roots, 13 supplemental findings, 23 seeded negatives, 8
  censuses; corruption probes PASS.
- Dashboard gates: `typecheck` PASS; `lint` PASS; `build` PASS with 3,885
  modules transformed, PWA precache 108 entries, post-build security PASS and
  Atlas UI Tailwind source PASS; `check:architecture` PASS with 0 dependency
  violations across 1,019 modules / 4,150 dependencies.
- Atlas UI gates: `typecheck` PASS; `lint` PASS; `check:architecture` PASS
  across 36 source files; `test` PASS, 18/18 files and 86/86 tests.
- Syntax/scope gates: `node --check` on the scanner, `py_compile` on the four
  touched Python files, JSON parsing for the package manifest and inventory,
  scoped Ruff `E,F,I,B,T20,N` on the new checker/test, and `git diff --check`
  all PASS.

The repo-wide command
`uv run polisyos-tools architecture guardrails check` remains inherited red on
the exact deep-import baseline drift for two `channel_contracts` edges, one
`lex_pipeline` edge, two `lex_search_projection` edges, and three removed
historical edges. P34 isolation was completed from an archive of exact clean
base `d6b38294e4f59a79ac3e7f6bf6bb5db2ea923f3f` at
`/tmp/polisyos-ds5-base.izNHaj`; the clean-base command reproduced the same
diff and five new-edge identities. An earlier `/tmp` archive attempt failed
before extraction with `fatal: not a git repository` and is a non-receipt; it
is not used as evidence.

### Pattern pass and self-review

- P27/P30: extended the existing TypeScript Program/TypeChecker engine and
  named the new entrypoint by its domain function; no sibling scanner or
  plan-named source was created.
- P29/P31: the checker recomputes both explicit production roots and follows
  symbols into the real `AuthorityBadge.presentation` sink; `lint:enforcement`
  executes that checker rather than checking marker text.
- P33: the exact namespace/wrapper/object/array/later-assignment/coercion/JSX
  witness and a shorthand-property corruption variant pass. Generated indexed
  owners, open terminal/evidence extensions, `BadgeTone`, responsive state and
  layout, and numeric width are executable benign controls.
- P34: the unrelated architecture red was excluded only after the clean-base
  archive reproduced it exactly.
- Review fix: the first live run falsely selected generated-indexed
  `FixtureAuthority` and its authority fields. The rule was narrowed by actual
  runtime-client declaration provenance, after which the 36-file live package
  returned `0 / 0` and both corruption/benign suites passed.
- Final measured scope: exactly eight changed paths (seven implementation
  files plus this journal), cap nine; no C02 path, canonical-owner gap,
  generated-contract change, fence escape, or capability-label promotion.

### Review fix pass 1 — declaration-bound provenance graph

#### Red-first receipts

The review tests and corruption witnesses were added before changing the
scanner. Each affected positive class failed against commit `034454b82`:

- Name independence:
  `test_sink_reachability_is_name_independent_and_unused_unions_are_benign`
  failed because `DecisionPosture`, `OutcomeMode`, and `ReviewPhase` were
  absent while unused `UnusedDecisionStatus` was falsely reported.
- Exact generated provenance:
  `test_generated_owner_requires_exact_governed_artifact_provenance` failed
  because both `LocalLookalike` and the prefix-only `PrefixLookalike` were
  absent. The governed direct and nested indexed controls remained benign.
- Per-field/call/carrier propagation: the required
  `test_package_namespace_alias_later_assignment_jsx_spread_revival_fails`
  failed with `ReviewPhase` absent after its explicit downstream type shortcut
  was removed. `test_owner_graph_is_field_call_and_carrier_sensitive` failed
  both the later-property-assignment and shorthand wrapper-returned-object
  witnesses; its discarded-argument, independent-sibling, removed-return, and
  removed-selected-field controls remained benign.
- Lifecycle sinks:
  `test_declaration_bound_lifecycle_sinks_preserve_owner_provenance` failed
  with both `disabled` and `aria-disabled` absent.
- `python3 architecture/atlas_surfaces/check_atlas_enforcement.py --check
  --corruption-probes` exited `1` with
  `name-independent-reachable-owners`,
  `exact-generated-artifact-provenance`, and
  `carrier-and-lifecycle-provenance` escaped.

Root cause: candidate discovery was gated by semantic name fragments,
generated provenance trusted an enclosing directory prefix, and one global
field-insensitive/call-insensitive taint set both promoted unused declarations
and collapsed argument, sibling-field, and return dependencies. The smallest
correct pattern is one per-owner reachability graph rooted in local closed
unions, with exact registered generated-artifact exemptions and
declaration-bound presentation/lifecycle sinks.

#### Repair and executable witnesses

- Candidate discovery now starts from every locally declared closed string
  union/enum or inline literal field in Atlas UI, independent of semantic name.
  Owners are emitted only when their individual owner ID reaches a real sink.
- Generated exemption paths come from the inventory's already content-bound
  `sources.generated_client.canonical_path` and `types_path`. Terminal type
  declarations are resolved cycle-safely; every leaf must equal one registered
  path. Local indexed lookalikes and `packages/runtime-api-client/fake.ts` fail.
- One field-sensitive symbolic graph carries per-owner atoms through parameters
  and actual returns, call-site substitution, selected object properties,
  constant array elements/destructuring, later variable/property assignments,
  shorthand fields, spreads, and nested wrapper-returned objects. Discarded
  arguments, independent siblings, separate call sites, overwritten spreads,
  and non-selected array elements remain benign.
- `AuthorityBadge.presentation`, `Button.disabled`, and
  `Button["aria-disabled"]` are accepted as sinks only when the JSX tag resolves
  to the exact Atlas declaration. Both direct attributes and JSX spreads are
  executable witnesses; `fullWidth`, `tabIndex`, layout booleans, and numeric
  controls remain benign.
- The required primary witness no longer annotates `later` as the Atlas owner
  type. Its package parameter/return, object selection, array, destructure,
  later assignments, shorthand object, and JSX spread are all load-bearing.
  Edge-cut controls for return, selected field, array, destructure, later
  variable, and later property each stop the sink.

#### Final green and gate receipts

- Post-Prettier focused/legacy battery:
  `python3 -m unittest architecture.atlas_surfaces.test_atlas_enforcement
  architecture.atlas_surfaces.test_status_retirement_inventory` — PASS, 43/43
  in `79.007 s`.
- Fresh DS4 checker: PASS in `29.805 s`; corruption probes PASS; 47 rows, 15
  current authored, 55 exemptions, 0 retirement debt, 3 waist debts.
- Fresh enforcement checker: PASS in `27.752 s`; corruption probes PASS; 36
  Atlas sources, 47 rows, 15 current authored, 0 owners, 0 sinks.
- Disposition checker: PASS; corruption probes PASS; 261 roots, 13 supplemental
  findings, 23 seeded negatives, and 8 censuses.
- Dashboard: typecheck PASS; lint PASS; architecture PASS with 1,019 modules /
  4,150 dependencies; build PASS with 3,885 modules and 108 PWA entries,
  post-build security and Atlas Tailwind checks PASS; `lint:enforcement` PASS
  with `36 / 47 / 15 / 0 / 0`.
- Atlas UI: typecheck PASS; lint PASS; architecture PASS across 36 sources;
  tests PASS, 18/18 files and 86/86 tests.
- Node syntax, Python compilation, scoped Ruff `E,F,I,B,T20,N`, Prettier,
  JSON parsing, workspace-link resolution, and `git diff --check` all PASS.

Repo-wide architecture guardrails remain inherited red on the same five new
deep-import identities: two `channel_contracts`, one `lex_pipeline`, and two
`lex_search_projection`, plus three removed historical edges. P34 isolation
from the full exact parent archive at
`/tmp/polisyos-ds5-fix-full-base.KbZiLN/policy-engine` reproduced exactly that
output. Three non-receipts are excluded explicitly: the eager all-field graph
was interrupted after about 90 seconds with exit 130 before optimization; the
first fix-pass archive used a nonexistent nested product path and reran in the
working tree; the product-subtree archive reproduced the deep-import identities
but also lacked parent workflow files. None is used as green or isolation
evidence.

#### Closeout pattern pass

- P29: the checker imports and runs the existing TypeScript Program/TypeChecker
  path against real declarations and executable corruptions; it does not grep
  markers. Removing a graph edge while retaining owner/sink names makes the
  corresponding witness benign.
- P31: one candidate-to-sink graph closes the class for arbitrary closed-union
  names and both registered sink kinds; no named-owner or per-consumer patch
  remains.
- P32: package prefix, name, shape, and present-but-fake declarations grant no
  exemption. Only cycle-safe terminal resolution to every exact governed
  generated artifact leaf does.
- P33: synonyms (`DecisionPosture`, `OutcomeMode`, `ReviewPhase`), local and
  prefix-only indexed lookalikes, sibling fields, overwrite order, distinct
  array indices/call sites, nested wrappers, direct/spread presentation, and
  direct/spread lifecycle sinks all execute.
- P34: only the full clean-parent archive receipt is used to exclude the
  repo-wide guardrail red.
- Final base-to-working scope is exactly the original eight paths, cap nine;
  the live denominator remains 36 and the DS4 estate remains `47 / 15 / 0`.
  No C02 path, canonical-owner gap, generated-contract change, fence escape,
  or capability-label promotion was introduced.

### Review fix pass 2 — complete proof and program-point ownership

#### Red-first and fixture-audit receipts

The pass-2 behavioral tests and matching corruption groups were added before
the scanner implementation changed. Their override sources were first compiled
through the real dashboard CompilerHost. Generated-branch, CFG/HOF, recursive,
lifecycle, and the required primary witnesses had zero diagnostics. The
program-point fixture initially produced two `TS2783` duplicate-prop warnings;
that parseable result is a valid failed fixture-audit receipt, excluded from
behavioral-red evidence. The test-only fixture was repaired with
content-known spreads whose erased static type preserves the same runtime JSX
overwrite order, then compiled with zero diagnostics. The intentionally invalid
override produced exactly one diagnostic at the override path: line 8, column
11, `TS2322`; it is a diagnostic-gate witness, not a behavioral red.

Against `6a62917e0cc35d82e234707a5e96cd18456f7454`, the named red results were:

- `test_generated_exemption_requires_every_union_branch_to_resolve` failed:
  `MixedDirect` and `MixedNested` were incorrectly exempted.
- `test_program_points_preserve_alias_identity_and_effective_jsx_overwrites`
  failed: alias, nested-alias, computed-read, and before-render owners were
  missed, while after-render and both overwritten owners were falsely retained.
- `test_cfg_handles_computed_keys_closures_control_flow_and_higher_order_calls`
  failed with all five expected closure/loop/switch/finally/HOF owners absent.
- The first eight-level recursive fixture passed as a valid characterization
  receipt but did not serve as a red witness: the old bounded summary loop
  happened to cover that depth. The strengthened
  sixteen-level `test_recursive_scc_reaches_fixed_point_without_depth_cutoff`
  then failed with `DirectRecursiveVector` absent while retaining its mutual
  recursion and benign controls.
- `test_lifecycle_sinks_derive_from_resolved_atlas_component_props` failed with
  both `SegmentDirectVector` and `SegmentSpreadVector` absent.
- `test_ds5_override_gate_rejects_invalid_witnesses` failed because the scanner
  emitted no override diagnostics. The paired legacy `_scan` remained free of
  the new field as required.
- The rewritten required primary
  `test_package_namespace_alias_later_assignment_jsx_spread_revival_fails`
  stayed green with a required props object and zero diagnostics; this is a
  characterization receipt, not a red.

`python3 architecture/atlas_surfaces/check_atlas_enforcement.py --check
--corruption-probes` exited `1` with exactly the five new groups escaping:
`mixed-generated-local-branch`, `program-point-identity-and-overwrite`,
`cfg-closure-higher-order-recursive`, `resolved-sibling-lifecycle`, and
`invalid-override-diagnostic`.

The first live run of the replacement completed as a valid failed gate receipt:
after `2:20.38` wall (`219.64 s` user, `16.40 s` system), V8 exhausted its
roughly 4 GiB heap before corruptions ran. A static cardinality profile counted
623 definition sources, 4,270 functions, 849 JSX roots, 815 eager global
non-function declarations, 6,243 allocation sites, and 15,415 call sites. Lazy
symbol-resolved global initialization removed the eager global root state; the
next complete live-plus-corruption command passed in `2:19.05` wall (`194.52 s`
user, `7.11 s` system) with `36 / 47 / 15 / 0 / 0`.

A temporary post-run state profile then measured 2,237 call contexts and 45,819
state clones copying 16,469,724 cell entries, 11,460,037 heap objects, and
27,937,570 heap properties. The largest and dominant context carried 1,580
cells, 1,113 objects, and 2,530 properties in both entry and exit; one locale
allocation site was replayed 326 times. That proved full-caller context capture
and wholesale exit replacement remained the dominant growth source.

Before changing that boundary,
`test_call_boundary_projects_captures_and_reachable_heap_effects` failed with
only the same-inner-call-site `InnerIsolationVector` falsely reaching the clean
second invocation. Its paired captured-cell mutation, argument-object mutation,
returned-fresh-object propagation, and clean strong overwrite already matched
their expected outcomes. This is the red witness for capture/heap-closure input
projection and effect-only output application; the existing recursive SCC test
remains its convergence control.

After that call boundary was projected, the same temporary live profile
completed in `21.333 s` wall (`31.08 s` user, `0.95 s` system). It retained all
849 JSX roots and grew to 3,303 finite caller-anchored contexts, but 36,104
clones copied only 194,825 cells, 98,818 heap objects, and 403,222 properties.
The largest clone fell to 43 cells / 112 objects / 485 properties; the dominant
context held one entry cell, 66 entry objects / 275 properties, and zero exit
cells, 67 exit objects / 292 properties. The instrumentation was then removed.

#### Structural repair

- Generated exemption resolution now returns a content-bound
  `{paths, complete}` proof. Every union/intersection/alias branch must terminate
  at the inventory's exact generated canonical/types paths; literal, local,
  unresolved, cyclic, mixed, and prefix-only branches fail closed.
- The copied-value/final-environment evaluator was deleted. Its single canonical
  replacement uses lexical symbol cells, owner/object/callable abstract values,
  allocation-site object identity, exact and dynamic heap keys, strong singleton
  and weak ambiguous writes, structured program-point execution, source-order
  JSX effective-prop folding, closure/HOF calls, and uncapped epoch-driven SCC
  convergence over a finite domain.
- Call contexts are finite caller-anchor/call-site pairs. Inputs contain only
  actual arguments, direct/transitive captures, callable closure captures, and
  their reachable heap. Outputs apply only captured-cell writes,
  input-reachable heap effects, and fresh return/closure-reachable objects;
  parameters and callee locals never leak into the caller.
- `AuthorityBadge.presentation` remains exact-declaration-bound. Lifecycle
  fields come from the central `LIFECYCLE_SINK_ATTRIBUTES` set plus the actual
  resolved Atlas component props type, including union constituents; no Button
  or SegmentedControl component list exists.
- Override diagnostics are opt-in at the DS5 enforcement call only, filtered to
  exact override paths, and sorted as stable path/line/column/code/message
  records. DS4 `_scan` requests and results remain unchanged unless explicitly
  opted in. Enforcement emits
  `invalid_source_override:<path>:<line>:TS<code>`.

#### Final-byte receipts

- Enforcement plus legacy unit battery: PASS, 50/50 in `181.525 s` (`3:03.04`
  shell wall).
- Status checker plus corruptions: PASS in `38.753 s`; 47 rows, 15 current,
  55 exemptions, 0 retirement debt, 3 waist-debt rows.
- Enforcement checker plus corruptions: PASS in `55.804 s`; 36 Atlas sources,
  47 rows, 15 current, 0 unauthorized owners, 0 unauthorized sinks. Separate
  live timing was `26.448 s`; the complete corruption-only suite was `22.823 s`.
- Disposition checker plus corruptions: PASS in `36.311 s`; 261 roots, 13
  supplemental findings, 23 seeded negatives, and 8 censuses.
- Dashboard: `lint:enforcement` PASS at `36 / 47 / 15 / 0 / 0`; typecheck,
  lint, and architecture PASS (1,019 modules / 4,150 dependencies); build PASS
  with 3,885 modules, 108 PWA entries, post-build security, and Atlas Tailwind.
- Atlas UI: typecheck, lint, and 36-source architecture PASS; tests PASS,
  18/18 files and 86/86 tests.
- Final syntax/hygiene: Node syntax; four-file `py_compile`; Ruff `E,F,I,B,N`
  on all touched Python and `T20` on the new checker/test; owner-scoped Prettier;
  both JSON parses; workspace links; and `git diff --check` all PASS. The
  repo-wide Ruff formatter reports the four baseline Python files would be
  reformatted; it made no edits and is not used as a required gate.

Repo-wide guardrails remain inherited red on exactly five new deep-import
identities: two `channel_contracts`, one `lex_pipeline`, and two
`lex_search_projection`, plus three removed historical edges. Fresh P34
isolation from exact base `d6b38294e4f59a79ac3e7f6bf6bb5db2ea923f3f` at
`/tmp/polisyos-ds5-fix2-full-base.l6ItUC/policy-engine`, with parent workflows
present and its own exact-base environment, reproduced exactly that output.

Excluded non-receipts are explicit: root `pnpm exec prettier --check` stopped
at its non-TTY dependency-purge prompt before Prettier ran; the first P34
archive used a nonexistent nested product path and reran in the working tree;
the product-only archive lacked parent workflows; reusing that archive's
executable kept its product-only repo root; and one full-archive dependency
install yielded without a retained session. None is used as semantic,
formatting, or isolation evidence. The parseable `TS2783` fixture-audit failure,
eight-level recursive green characterization, and live V8 OOM are valid failed
or characterization receipts, not non-receipts.

#### Closeout pattern pass and self-review

- P29/P33: all gates execute the real Program/TypeChecker, heap/CFG/call path.
  Branch synonyms, malformed/invalid overrides, mixed generated/local proof,
  alias identity, computed/dynamic keys, both JSX overwrite orders, before/after
  program points, closure/loop/switch/finally/HOF, direct/mutual recursion,
  call-boundary effects/isolation, and generic sibling lifecycle controls are
  executable adversarial witnesses. Removing an edge while retaining markers
  changes the result.
- P31: one evaluator closes the class; the superseded copied-value evaluator and
  temporary profiling instrumentation are absent. There is no named-owner,
  component-list, source-list, context-cap, or heap-limit bypass.
- P32: authority is admitted only through exact generated branch completion,
  exact resolved sink declarations/props, and diagnostic-clean DS5 overrides;
  form, prefix, local lookalikes, and partial proof cannot self-attest.
- P34: only the final full-base archive receipt excludes the inherited guardrail
  red; every incomplete isolation attempt is named above.
- Capability state remains the existing enforcement verification/surface; no
  C02 contract or capability label was promoted. Base-to-working scope is the
  original exact eight paths, cap nine, with no canonical-owner gap, generated
  contract change, fence escape, or owner-path expansion.

## DS5-C10 — deferred owner integrate contract

- **Disposition:** deferred on 2026-08-02; this downstream gap does not block
  C01-C09 or C11 onward.
- **Typed debt:** `g4-complete-audience-projection-contract` records
  `team-runtime-quality` as owner, the five incomplete capability states, the
  exact eight-field projection contract, EXPERT `mode.analyst` authorization,
  provenance/hash/time/novelty requirements, and the executable owner-side
  closure signal.
- **Owner evidence:** the current G4 contract remains `projection_only`, route
  unregistered, and `out_of_scope_reference_only`; DS5 does not route or
  reclassify the raw owner artifact.
- **Register receipt:** the byte-preserving supplemental writer and report
  writer completed; the live checker returned 261 roots, 14 supplemental
  findings, 23 seeded negatives, and 8 censuses.
