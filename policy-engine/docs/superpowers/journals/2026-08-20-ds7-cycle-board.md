# DS7 Cycle Board execution journal

Date: 2026-08-20
Branch: `codex/atlas-ds7-cycle-board`
Approved spec: `docs/superpowers/specs/2026-08-20-ds7-cycle-board-design.md`
at `4eec3fb48`

This journal records measurements and rulings. It does not revise either
programme plan, mint producer authority, or claim a release-owner compatibility
decision.

## Cluster 0 — GAP4 and generated clients

### Preserved merge state

- Attached HEAD before the GAP4 commit:
  `40ef040bd6ecc5b652bf0498ba5abe20977fed76`.
- Uncommitted GAP4 merge parent:
  `4147384c8951930190076263c8b99672d7352023`.
- The merge remains intentionally open until OpenAPI, both complete client
  families, the compatibility fragment, and all invalidated governed receipts
  can land in one commit.
- No Atlas register lock was held during install, generation, the P41 replay,
  or drift classification.

### Toolchain gate

`corepack pnpm install --frozen-lockfile` completed with exit 0 in 1.3 s under
a fixed 180 s ceiling; pnpm reported version 10.33.2 and an up-to-date six-project
workspace. Host load was `3.13/3.17/3.36` before and after. The dashboard
`prepare` script reported installing Lefthook into the worktree's shared Git
common directory at `/Users/deniskopylov/polisyos/.git/hooks`; no root-checkout
tracked file was entered or edited, and DS7 does not inspect or alter that
shared metadata further.

This completed gate admits the TypeScript AST and generated-owner measurements
below. Earlier unbootstrapped scanner attempts remain non-receipts.

### P41 no-GAP4 falsifier

The control is an independent temporary clone, not a nearer base and not a
sibling worktree:

- exact clean HEAD `40ef040bd6ecc5b652bf0498ba5abe20977fed76`;
- GAP4 absent;
- `corepack pnpm install --frozen-lockfile` completed before scanning;
- both canonical commands completed with exit 0:
  `corepack pnpm --filter @polisyos/runtime-api-client run generate` and
  `corepack pnpm --filter @polisyos/runtime-dashboard run generate:api`.

Raw identities:

| Artifact | Committed `40ef040bd` | Regenerated without GAP4 | Preserved GAP4 regeneration |
| --- | --- | --- | --- |
| OpenAPI | `f94c87d56cf1cc3658c3c9330bd202fc2061fc2debad16a407d0aabf322cb0cb` | same | `6f4dd9511fd7b4c9e15b398812fbe5bd70e7da91ff7a50113c6131493d236d1c` |
| package `types.ts` | `137ba30652cc89ff37317d055ab63704e0ccdfdb705e618851fb7ed2f015e644` | same | `e290256295f9e567005775ffcbb9771d2e514bbae9cfc34ab7075417b48317d1` |
| dashboard `types.ts` | `813cf59f7536647dd74d0743b3f0e58b0c850e9ecab125f4f2ed691ba38b18a0` | `95e106c363d9cb7230ff9973a6505cad8c3c22b4db9d2a808c466773cef49b98` | `078f5edd3fa89b5dda4d59d45abd6842d9cd215d5917ddefbca4c78467cfadca` |

The installed TypeScript AST census normalizes every property signature by
containing export, full structural path, optionality, and semantic-node hash.
Both families keep five top-level exports, every pre-existing export survives
exactly once, and no export is added, changed, removed, or duplicated.

#### A. Committed slice base → regeneration without GAP4

| Family / containing export | Fields before → after | Unchanged / changed / removed / added |
| --- | ---: | ---: |
| package total | 8,165 → 8,165 | 8,165 / 0 / 0 / 0 |
| package `paths` | 1,274 → 1,274 | 1,274 / 0 / 0 / 0 |
| package `components` | 2,811 → 2,811 | 2,811 / 0 / 0 / 0 |
| package `operations` | 4,080 → 4,080 | 4,080 / 0 / 0 / 0 |
| dashboard total | 7,672 → 8,165 | 7,632 / 40 / 0 / 493 |
| dashboard `paths` | 1,232 → 1,274 | 1,232 / 0 / 0 / 42 |
| dashboard `components` | 2,522 → 2,811 | 2,518 / 4 / 0 / 289 |
| dashboard `operations` | 3,918 → 4,080 | 3,882 / 36 / 0 / 162 |

The only changed pre-existing leaf is dashboard
`components.schemas.AuthMeResponse.permissions`, line 2323 → 2481,
`string[]` → `components["schemas"]["RuntimePermission"][]`. The other 39
changed records are derived containers; no pre-existing field path is removed.
The six governed TypeScript anchors resolve with offsets `{0,+158}`; only the
dashboard permissions anchor moves.

Verdict: the dashboard family was already stale at the slice base. This
`changed-or-removed` regeneration is inherited from DS20-era permission
vocabulary projection and is not introduced by GAP4.

#### B. Regeneration without GAP4 → regeneration with GAP4

| Family / containing export | Fields before → after | Unchanged / changed / removed / added |
| --- | ---: | ---: |
| package total | 8,165 → 8,167 | 8,163 / 2 / 0 / 2 |
| package `paths` | 1,274 → 1,274 | 1,274 / 0 / 0 / 0 |
| package `components` | 2,811 → 2,813 | 2,809 / 2 / 0 / 2 |
| package `operations` | 4,080 → 4,080 | 4,080 / 0 / 0 / 0 |
| dashboard total | 8,165 → 8,167 | 8,163 / 2 / 0 / 2 |
| dashboard `paths` | 1,274 → 1,274 | 1,274 / 0 / 0 / 0 |
| dashboard `components` | 2,811 → 2,813 | 2,809 / 2 / 0 / 2 |
| dashboard `operations` | 4,080 → 4,080 | 4,080 / 0 / 0 / 0 |

The only added leaves in each family are
`components.schemas.RunSummary.run_terminality` and
`components.schemas.RunTerminality`. The two changed records in each family
are only their derived containing properties
`components.schemas` and `components.schemas.RunSummary`. There is no changed
pre-existing leaf and no removed field.

| Governed anchor | No-GAP4 line | GAP4 line | Offset / content |
| --- | ---: | ---: | --- |
| package `RunSummary` | 9240 | 9240 | 0; derived container changes |
| package `finished_at` | 9259 | 9259 | 0; unchanged |
| package `status` | 9285 | 9286 | +1; unchanged leaf |
| package `AuthMeResponse` | 2414 | 2414 | 0; unchanged |
| package `AuthMeResponse.permissions` | 2430 | 2430 | 0; unchanged |
| dashboard `AuthMeResponse.permissions` | 2481 | 2481 | 0; unchanged |

The GAP4 offset set is `{0,+1}`; the single post-insertion offset is uniformly
`+1`. GAP4's net contribution is therefore **`additive-and-declared`**.

### Generated-family ownership defect

A complete `architecture/generated_artifacts.toml` census contains 59
families. The dashboard `types.ts` has exactly one declared output owner,
`runtime-dashboard-api-types`, with `drift_gate = automated` and
`stale_output_behavior = "fail"`. The current package `types.ts` has zero
declared output owners; `runtime-api-client` lists only raw TS/JS although its
canonical package command also emits `types.ts` and canonical TS/JS.

The ordinary architecture check executes generated-family commands only when
`--run-generated-checks` is present. This explains how declarations could be
validated without exercising the stale bytes; whether a particular historical
CI run skipped or failed is `not_established`.

The inherited defect is registered as `GY-DEF20` in the Atlas inherited-debt
table with owner `team-polisyos` and an executable corrupt-output closure
signal. It is not repaired inside DS7.

### Permission-consumer migration scope

The current dashboard contains twelve owner-valid permission literals and zero
`collaboration.comment`, `collaboration.share`, or `collaboration.view`
source occurrences. DS5 already changed `PermissionKey` to generated
`RuntimePermission` and constrained the remaining list with
`satisfies readonly RuntimePermission[]`. The three orphans therefore have
typed refusal by exclusion and no live call site at which a cast, substitute,
or invented permission could be added.

The complete regenerated dashboard typecheck finished with exit 0 in 15.1 s
under a fixed 180 s ceiling. Load was
`3.21/3.42/3.57 → 3.32/3.43/3.57`. The required permission-migration write
set is exactly zero. The wider twelve-literal duplication and the adjacent
string-valued `/auth/me` validator remain reported and out of scope.

The existing C07b receipt test still pinned the stale dashboard field as
`string[]`. Its assertion is migrated to the regenerated
`RuntimePermission[]` shape while the separate single-owner debt stays open:
the local client and its 27 non-test importers still exist. This is the same
inherited `GY-DEF20` staleness class, not a DS7 mechanism finding, and consumes
no round.

### P39-corrected review accounting

The P41 inherited-staleness finding is not against DS7's mechanism and consumes
no round. The first compatibility-fragment review found
`compatibility-claim-evidence-overreach`: DS7 had asserted a
release-owner compatibility verdict, described the whole dashboard rewrite as
additive, omitted the governed runs-channel example `v1 → v2` change, and had
not bound the fragment to this measured receipt.

Delta-only review accepted that repair and then found the same class one level
deeper: prose impact labels were not categorical compatibility declarations.
The widened repair uses only `additive` and `requires_regeneration` in impact
fields, leaves the release-owner ruling pending, separates inherited dashboard
staleness from GAP4's additive pair, and binds the governed example change and
`GY-DEF20`. The second scoped delta review marked the finding addressed and
found no new breakage. The architect's P39 falsifier refunded both originally
charged rounds: the compatibility fragment is a mandated record, and
subtracting it from the measured cut leaves neither finding against the merge,
regeneration, re-anchoring, board, producer, or mechanism test.

The full pre-lock review then found contradictory historical plan text: it
still described the lifecycle producer as missing after the descriptor had
transitioned to DS7 consumer debt. The first delta review rejected the claimed
zero-round exception because its receipt was not recorded and also found two
stale line anchors. The widened static-record repair has this exact receipt:

- immutable base / current worktree: `40ef040bd6ecc5b652bf0498ba5abe20977fed76`
  with preserved `MERGE_HEAD 4147384c8951930190076263c8b99672d7352023`;
- complete tracked denominator: `git ls-files -z | tr -cd '\0' | wc -c`
  returned 9,885 files;
- `git grep -n -F 'no producer-signed terminal/completion fact'
  40ef040bd6ecc5b652bf0498ba5abe20977fed76 -- .
  ':!docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md'`
  and the same current-tree query each returned zero external hits;
- the binding-key census `git grep -n -F 'run-lifecycle-terminal-fact' -- .`
  returned 11 lines in seven tracked files. It exposed two current Atlas-plan
  statements, so both the inherited-debt row and the DS7 gate are reconciled;
  historical revision/journal statements remain historical, and the governed
  register/report transition inside the lock;
- a complete code/test path search for the Atlas master-plan filename across
  `architecture/**/*.py`, `tests/**/*.py`, `apps/**/*.ts`, `apps/**/*.tsx`,
  `src/**/*.py`, and `tools/**/*.py` returned exactly two lines in one checker:
  a static evidence reference and `controlled_vocabulary_source` metadata,
  neither a plan-content reader or test dependency;
- opening SHA-256s remain register
  `8de4da1e7fe6b46146a83371c37391295c78852cde823c4f847dfa0d8d934a65`,
  report `699c3b0938807b7a84fc107efcf56652426cad2a8e3545258c8e656b04d4ab72`,
  status inventory
  `7021051344444a1cc6c50ca91bc935c84ee2f9db9f6e8a33f12d8e95151572b5`,
  baseline manifest
  `08ae63cbd6c31bd582a5b12a5bd45edfe9078425f7102c33dbfddb0c26865d0d`,
  and readiness ledger
  `4b64f0920154803fa87e96f27f0c97afb8933e17c2dcd78a958a99af78e2ae13`;
  the five-path `git diff --name-only` denominator was empty.

The plan now records live package anchors 9240/9259/9286 and the
GAP4-producer-present / DS7-consumer-missing state in both current statements.
Because this repair changes no behavior, test outcome, or governed artifact
byte, it meets the explicit static-diagnostic zero-round exception rather than
consuming a mechanism round. Mandated-record findings are still repaired and
reviewed; they are simply outside the mechanism budget when that byte/outcome
predicate is proven.

### Derivable generated-client receipt denominator

The first mechanism review had enumerated six TypeScript identities but missed
eight status-inventory line bindings. Root classified that as the first
mechanism finding (`1/2`); the reviewer reported the escape and assigned no
round.

The red-first test
`architecture/atlas_surfaces/test_generated_client_receipt_census.py` failed
three of three cases only because its production module was absent. The
implemented
`architecture/atlas_surfaces/generated_client_receipt_census.py --check`
derives every Git-visible JSON/TOML candidate, then reconciles two populations:
explicitly anchor-named symbol/line records and every target-associated
line-coordinate record regardless of parent key or symbol vocabulary. Its
negative introduces a `future_binding` carrying only `type_name` and line
coordinates; the independent census finds it and the checker fails closed with
an artifact-and-pointer-specific `anchor_population_mismatch`.

The delta review found the first implementation conflated navigation with
binding, did not enumerate record identities, shared its symbol convention
between both populations, and relied on manual invocation. Root classified
this as the same P35/P38 mechanism class one level deeper (`2/2`) and widened
the repair once: bindings and navigation are separate lists, every record is
enumerated with artifact/pointer/owner/symbol/field/targets/coordinates, the
independent derivation requires no symbol or anchor key, and
`check_status_retirement_inventory.py` now consumes the report. The command
gate has a negative proving a census disagreement changes its exit to failure.

P40's bounded residual is explicit after that widened repair: the independent
census recognizes a structured line binding only when the artifact exposes an
integer coordinate with a distinct `line` token and associates the record with
a regenerated target path. It cannot infer an opaque integer whose schema and
key never declare line or target meaning. The smallest capability that would
close that unknowable case is a normalized repository-wide line-binding schema
or registry; the complete current tree has no such owner, and inventing a
remembered list here would recreate the defect. The falsifier varies both
container and symbol vocabulary (`future_binding` + `type_name`) while retaining
declared line/target semantics; a future unmarked representation is
`not_established`, not silently counted as governed.

Live completion returned exit 0 and this full denominator:

| Quantity | Count |
| --- | ---: |
| Git-visible JSON candidates | 1,176 |
| Git-visible TOML candidates | 199 |
| candidate-path manifest SHA-256 | `5f77930ad765e6361ad0095d8e5e70c56f35b400491d04b56da22fb4928c195f` |
| binding artifacts | 2 |
| independently reconciled structured records | 18 |
| structured integer bindings | 38 |
| navigation-only artifacts | 2 |
| separately enumerated `target:line` navigation references | 38 |

The binding artifacts are the DS4 waist register (3 records / 8 bindings) and
status inventory (15 records / 30 bindings). The frontend disposition register
(1 reference) and readiness ledger (37 references) are reported separately as
navigation-only and never inflate the binding denominator. This census is
reusable before future generated-client changes and no governed artifact
filename is remembered in the receipt population.

### Status-inventory line-address defect and temporary re-anchor

The complete status population is 15 generated anchors. Eight and only eight
moved on the GAP4 regeneration; each resolved to the same symbol and field,
with the uniform offset canonical `+2` / schema `+7`:

`status-workflow-node`, `status-quantity-provenance`, `status-scenario`,
`status-verification`, `status-dispute-quantity`,
`status-dispute-trust-view`, `status-inline-small-multiples`, and
`status-inline-counterfactual-badge`.

Those eight receive a one-time mechanical receipt refresh inside the open lock
window. This is mandatory record maintenance, not identity-safety closure;
repeated or scheduled re-anchoring remains forbidden. The surviving
`DS5-LINE-ADDRESS-01` / P38 class is registered as `GY-DEF21` beside
`GY-DEF20`, owned by DS5. Closure requires a uniquely resolvable construct
identity, or navigation-only line numbers that cannot fail on movement;
longer lists, tolerance windows, ranges, and scheduled re-anchoring are
explicitly forbidden.

After re-anchoring, the status checker completed in 16.4 s with exactly the 13
diagnostics reproduced at immutable base `40ef040bd` in the isolated clean
clone `/tmp/ds7-status-p41.HVBRho/repo/policy-engine`: one
`live_status_denominator_drift`, eight
`unregistered_semantic_definition`, and four
`unregistered_status_definition`. The eight current-only
`generated_anchor_drift` diagnostics are gone. This is green-except-the-exact
13 inherited diagnostics, not an absolute-green claim.

### Mandated navigation-record reconciliation

The first post-regeneration constant refresh incorrectly carried a 15-line
denominator. An independent walk of the exact `_live_references` population
showed why: `apps/runtime-dashboard/src/api/types.ts:7050` was already present
at immutable `40ef040bd`; the DS7 descriptor replaces two numbered evidence
references with three unnumbered paths. The reconciled live population is:

- 261 total references;
- 12 line/navigation references across 10 files;
- extension partition TS 6 / 4 files, PY 4 / 4 files, MD 2 / 2 files;
- 12 descriptor-evidence line references and 12 writer residuals;
- five structured identities, unchanged.

The checker and constant-pinning tests now derive and pin that population.
This repair changes no mechanism byte or test property and was independently
reviewed as a mandated-record correction, so it consumes no round under the
P39 split.

### Final Cluster 0 verification receipts

The source was frozen before the final wave. Non-contended suites ran in
parallel; the frontend register checker was the only long delta run and used a
fixed 150 s ceiling with load recorded as
`2.59/2.78/2.93 → 4.16/3.58/3.25`. No ceiling was enlarged and no process was
killed.

| Receipt | Result | Duration / fixed ceiling |
| --- | --- | --- |
| OpenAPI regeneration | exit 0; hash unchanged at `6f4dd951…236d1c` | 10.006 s / 90 s |
| package client regeneration | exit 0; all five package output hashes unchanged | 1.778 s / 150 s |
| dashboard client regeneration | exit 0; hash unchanged at `078f5edd…adca` | 2.802 s / 120 s |
| runtime API contract | exit 0 | 13.127 s / 240 s |
| package generated-client test/typecheck/lint/architecture | exit 0; 4/4 generated-client tests | completed |
| dashboard typecheck/contracts | exit 0; 1/1 contract test | 21.921 s for typecheck |
| mandatory compatibility release gate | exit 0 | completed |
| frontend register check + baseline bytes + corruption probes | exit 0; corruption probes PASS | 130.494 s / 150 s |
| receipt-census/status-entry/navigation focused tests | exit 0; 7/7 | 34.464 s / 120 s |
| `git diff --check` | exit 0 | completed |

The direct status-checker invocation first exposed a real import-boundary RED:
executing the documented script path could not resolve the package-qualified
census import. The narrow fix falls back to the sibling module only when the
missing module is exactly `architecture`; nested import failures still raise.
The direct-entry negative and command-consumption negative pass.

Ruff was initially a tooling non-receipt because the local venv had no module.
Running through `uv --with ruff` completed. The exact four inherited Atlas
files report 654 diagnostics at both immutable `40ef040bd` and current bytes,
with identical per-code counts; the two new census files report zero. Thus the
lint gate is baseline-red with zero new diagnostics, not green.

The final status comparator completed in 36.069 s under the unchanged 90 s
ceiling. Its raw exit is 1 with exactly 13 diagnostics, SHA-256
`511bfd68fea9232d15e33a577859121ca61501a4824a8535ccfd16551ffa17f9`,
and empty current-only/base-only sets. The first comparator attempt read stdout
while the checker emits diagnostics on stderr; that attempt is a harness
non-receipt, not a duration or product finding.

The broader wave retains, rather than relabels, inherited reds:

- the GAP4-focused API suite is 65 passed / 2 failed, with both failures
  reproduced at exact `40ef040bd`;
- architecture guardrails retain the same six edges reproduced at the slice
  base;
- the full focused Atlas set retains three exact base failures while the two
  current-only navigation constants are repaired and pass in the delta suite;
- DS8 A4 print, DS5's stable run-deck `1094x821` versus governed `1094x820`,
  and DS6-C11 remain inherited red and are not reported green.

### Register-family lock close protocol

The lock was held only for Cluster 0's atomic merge/regeneration/re-anchor
window. Its identities are:

| Artifact | Opening | Closing working-tree bytes for the atomic commit |
| --- | --- | --- |
| disposition register | `8de4da1e…934a65` | `21914b85…03dba` |
| generated report | `699c3b09…4ab72` | `426e87b0…d5a5a` |
| status inventory | `70210513…572b5` | `a970fe0c…c8c45` |
| baseline manifest | `08ae63cb…65d0d` | unchanged |
| readiness ledger | `4b64f092…e2ae13` | unchanged |

The atomic commit is the lock-release boundary. Relinquishment occurs only
after these five identities are read back from the attached branch; no later
register-family write is implied by this record.

## Inherited-red provenance receipts — reds before board mechanism

Task 2 replayed the exact owner commands at the slice base
`4456bb885fbec62657e8ee55d3d35aac89c08713` and the attached pre-board head
`d588b5a137627c2c1e4b5df8d29890d16cc93c42`. The base was materialized as an
isolated detached clone at `/tmp/ds7-base4456.zIUBqQ/repo`, not as a worktree
and without touching another lane. Its toolchain gate,
`corepack pnpm install --frozen-lockfile`, completed in 9.691 s with pnpm
10.33.2 and 1,211 packages before any TypeScript or browser result was admitted.

The visual source/config/fixture censuses are navigation evidence, not complete
behavioral denominators: DS8 has 10 direct paths and DS5 has 23 direct paths,
all byte-unchanged from the slice base, while the full transitive Vite/runtime
input graph is `not_established`. Exact-base replay proves that both visual
reds predate DS7, and their registered owner dispositions remain unchanged; it
does not establish DS7-to-red input disjointness or a complete P41 ownership
proof. Playwright, Storybook, and their fixed ports were serialized; retries
were zero; no snapshot writer or `--update-snapshots` was used.

| Owner red | Exact-base receipt | Attached-head receipt | Fixed ceiling |
| --- | --- | --- | ---: |
| DS8 A4 print | exit 1, completed in 91.847 s; expected `724x2113`, actual `770x13269`, 692,128 differing pixels | exit 1, completed in 23.579 s; same dimensions, 692,156 differing pixels | 2,400 s |
| DS5 run-deck | exit 1, completed in 13.624 s; expected `1094x820`, actual `1094x821`, 4,178 differing pixels | exit 1, completed in 13.373 s; same dimensions and 4,178 pixels | 90 s |
| DS6-C11 focused component file | exit 1, 21/22 in 16.931 s; sole failure at `atlasHealthMetrics.test.ts:649` | exit 1, 21/22 in 15.261 s; the same sole failure | 90 s |
| complete dashboard component population | exit 1, 1,188/1,189 in 534.067 s; sole failed identity `Atlas health metrics > persists the producer-observed report and snapshot through Core CAS` | exit 1, 1,188/1,189 in 550.594 s; the same sole failed identity | 1,800 s |

The paired load receipts were:

- DS8 base `3.35/3.57/3.61 -> 4.47/3.75/3.66`; attached
  `3.56/3.63/3.62 -> 3.95/3.71/3.65`;
- DS5 base `4.22/3.73/3.66 -> 4.18/3.75/3.66`; attached
  `3.42/3.60/3.61 -> 3.35/3.57/3.60`;
- DS6-C11 focused base `3.03/3.49/3.57 -> 3.45/3.55/3.59`; attached
  `3.03/3.49/3.57 -> 3.32/3.53/3.58`;
- full population base `3.11/3.43/3.54 -> 4.47/5.47/4.79`; attached
  `3.11/3.43/3.54 -> 4.31/5.38/4.77`.

The governed DS8 expectation is byte-identical at base and attached head,
SHA-256 `a920f6c95aead95c1126838d2eebd7ed1410fad10cf8f8e6f05d9b848f79217d`.
Its actual images are not byte-identical
(`8a43990c…dce0cf` versus `354ec311…0bbdc`), so the receipt claims the
same inherited dimensional failure and not pixel determinism. The DS5
expectation is byte-identical at
`76ecd68a93dd843940212f73392f080704ae17dea87be5f8a358f337c15d9aaa`;
both actual images are also byte-identical at
`823fffa7f72433bdb8c1a141c9f38b1b2da7d8bbd28652755dada8abdfa3053f`.

DS6-C11's complete dynamic owner-input denominator is 17 paths: six direct
implementation inputs, ten validated source references, and the C12 protocol.
Cluster 0 and its current-main merge intersect that set at zero. The full slice
base-to-head diff intersects it only at
`architecture/policy_design_case/inventory.json`, an inherited main movement
before Cluster 0; the exact-base and attached full-population replays then
produce the same sole assertion, `expected [] to deeply equal
ArrayContaining{...}`. Thus DS6-C11 remains red and owner-attributed rather
than being inferred from a static zero.

All eight invocations — four command forms at two refs — completed. No kill is
reported as a duration sample and no ceiling was enlarged. These receipts
preserve the three inherited reds:
DS8 A4, DS5's `1094x821` residual against `1094x820`, and DS6-C11.
None is reported green. This journal-only P41 record changes no mechanism byte,
governed expectation, or test outcome and consumes no mechanism round under
the corrected P39 split.
