# Debt G — Atlas Residuals Execution Journal

Date: 2026-08-30
Branch: `codex/debt-g-atlas-residuals`
Base: `784d02014`
Plan: `docs/superpowers/plans/2026-08-30-debt-g-atlas-residuals.md`

## Scope and preservation

This lane owns eleven residual rows and may not edit the debt register, generated
ledger, Atlas master plan, GY plan, or published debt denominator. Under the runtime
dashboard it owns only `scripts/persist_atlas_evidence.py`; task D retains all app
source and the frontend-disposition test module. Corrections append. Routing is
never treated as ownership.

## Pattern pre-pass

Relevant register patterns are P01/P02 (contract or routing without a real bridge),
P03 (hidden DS18 richness), P29/P32 (marker or form as proof), P35/P36 (sampled
denominator and authority by adjacency), P37/P38 (declared/proxy gate predicates),
P39 (mandatory companions), P40 (same-class ladder repair), and P41 (red
provenance). The target pattern is a live enforcement bridge, a Git/content-bound
historical mapping, an independently replayed DS18 predicate, and append-only
argument evidence.

## Initial complete-row read

All eleven primary register rows were read in full before planning. The later
append-only occurrences of `ds4-waist-decision-grade` were also read. The initial
capability states are not collapsed: DS4 is still `surface_missing`; the three
DS8 scope rows are `absent/unallocated`; DS6 has an established TypeScript producer
but a stale Python admission projection; the timing row is
`verification_missing`; the two task-C overlaps keep producer and Atlas-scope
halves separate.

## Measurements before implementation

### Frontend baseline bindings

The canonical current field is `lint.resolution_content_bindings`, validated by
`architecture/atlas_surfaces/check_frontend_disposition_register.py`; the older
`resolutions[].origin_identity.source_content_sha256` coordinate still exists in
75/75 resolution rows but is not the current content-binding field. A complete
direct walk found 46 binding rows over 45 unique paths: 2 `.cjs`, 14 `.ts`, and 30
`.tsx` binding rows, with zero current SHA-256 mismatches. All six paths named by
the debt row are fresh. A full checker invocation was an environment non-receipt
before `uv sync` because `jsonschema>=4.25` was absent; it is not used as the
binding verdict.

### DS5 successor table

The complete `DS5-enforcement-waist.md` handoff table contains 27 groups over 58
sites. The six historical handoffs comprise 6 groups/11 sites: DS12 3/7, DS14 1/1,
DS15 1/1, and DS18 1/2. Current planless successors are DS12 3 groups/7 sites and
DS14 1/1: 4 groups/8 sites. DS15 1/1 and DS18 1/2 now have standalone plans but the
exact group labels are not absorbed into their plan text.

### Generated DecisionGrade

The PDC owner still declares `DecisionGrade`, while the OpenAPI and generated
clients carry inline four-value enums/unions. Across the two registered generated
artifact families and their six outputs there are zero named `DecisionGrade` alias
occurrences. The next-regeneration swap has not happened.

### Timing workload identity

The requested single pytest node failed before repair at `67 == 232`: 191
source-declared tests in `test_frontend_disposition_register.py` plus 41 in
`test_status_retirement_inventory.py`. A real current pytest collection is a
different canonical form: 194 + 41 = 235 runnable node IDs, SHA-256
`ede7f43cb4f88b325950e5a958eb0efc7050837717038404a816987f3279fab3` for the
newline-joined ordered IDs. The register separately preserves 181, 190, and 210.
These are one workload-identity defect, not candidate totals to choose among.

At publication commit `6bcc95bff32645189ff2ed65a719c7990e48c52a`, the two
historical test blobs expose 30 + 37 = 67 source-declared unittest node IDs. The
binding repair will attach the receipt to that complete ordered historical mapping
and its Git source, not to today's population.

### DS18 projection

The current register contains 621 production TypeScript files and 759 render/export
roots. It classifies 126 roots as decision-bearing or inherited and covers all 126;
every file/root predicate provenance is `independently_reconciled`, and a direct
content walk found zero file SHA-256 mismatches. The older 605/719/77/77 and
616/733/94/94 receipts are dated source freezes, not current totals. The Python
persistence adapter alone still hard-codes primitive adoption as unknown.

## Rulings

- Ruling: the detailed task brief is the approved design constraint for this
  maintenance lane; no separate brainstorming approval pause is needed. Cost if
  wrong: the user may prefer a different manifest surface and the small mechanism
  would need rework.
- Ruling: all three DS8 obligations are inputs to each of DS12, DS13, and DS14
  scope setting. The gate demands the complete three-row input set from every one
  of those target plans. Cost if wrong: a later plan may carry redundant input
  acknowledgements, but no row will be falsely closed.
- Ruling: the timing sample is historical. Bind its immutable publication snapshot
  and exact node map; do not mutate a completed duration to follow current test
  growth. Cost if wrong: the architect may instead require a fresh timed sample,
  in which case the historical mapping remains valid evidence but the catalog
  needs a new owner-controlled sample.

## Execution ledger

Implementation and review receipts append below. The final section of this file is
reserved for the eleven-block Register closure dossier.

### Task 1 — DS8 residual scope-obligation gate

Implemented a strict `slice-scope-obligations` manifest and schema, then wired a
live validator into `check_atlas_enforcement.py`. The manifest is the sole
enumeration of the three DS8 residual IDs; it explicitly makes acknowledgements
`candidate_only` with `closure_effect: none`. The validator walks every tracked
Markdown plan, parses complete YAML frontmatter, identifies a target only by
`type: slice-plan` plus `slice`, and requires the exact unique
`atlas_residual_inputs` set. Missing DS12/DS13/DS14 plans remain open and green;
multiple plans for a target fail.

RED receipt: after the focused environment setup, the five new unittest nodes
failed with `AttributeError` because `validate_slice_scope_obligations` and
`_tracked_atlas_plan_paths` did not yet exist. The first collection attempt was
an environment non-receipt (`ModuleNotFoundError: jsonschema`); the authorized
locked setup was `uv sync --frozen --extra test`.

GREEN receipt: the same five focused nodes passed (`Ran 5 tests ... OK`). The
live `uv run python architecture/atlas_surfaces/check_atlas_enforcement.py
--check` completed with exit 1 from unrelated Atlas inventory/authority,
source-denominator, query-cache, status, and architecture-graph checks; their
provenance was not re-established in this task. It emitted no
`slice_scope_obligation_*` error. One accidental non-PTY duplicate checker process
was terminated, leaving one PTY-backed authoritative receipt.

### Task 2 — historical Atlas timing workload identity

The pre-repair focused node was red: the completed receipt's `67` tests passed
count was compared to the current helper-derived AST count, `191 + 41 = 232`.
This is distinct from the inherited register derivations `181`, `190`, and `210`,
and from current pytest collection, `194 + 41 = 235` node IDs. The current forms
evidence growth; none selects a replacement count for the historical sample.

The repaired test resolves the publication commit
`6bcc95bff32645189ff2ed65a719c7990e48c52a`, reads precisely the two paths named
by the catalog command, and derives their ordered pytest node IDs from supported
unittest forms. It content-binds the historical frontend blob to
`841466263c618a3142a6d5327c72072ad0e95bf4d738516f6d240eb98601b685` (30 IDs),
the status blob to
`7f5418b7e809b1f1bac0470ecc2a553c878b14d886ea39494362067908e7ca0f` (37 IDs),
and compact canonical JSON of their complete ordered 67-string map to
`9b08f0ed2e74bf888009820529e2901c6dd3bedb40bf55a679a362efaf12aea6`. It rejects
duplicate node IDs and decorated forms whose runnable cardinality cannot be
derived exactly. The cited receipt remains `67` tests passed.

RED receipt:
`uv run --extra test --with 'jsonschema>=4.25' python -m pytest tests/repo_quality/tools/test_timing.py::test_atlas_python_governance_lane_names_one_exact_runnable_workload -q`
exited 1 with `AssertionError: assert 67 == 232`. The new test expectation then
failed with the expected missing-helper `NameError` before implementation.

GREEN receipt:
`uv run --extra test --with 'jsonschema>=4.25' python -m pytest tests/repo_quality/tools/test_timing.py::test_atlas_python_governance_lane_names_one_exact_runnable_workload`
exited 0: `1 passed in 0.13s`.

### Task 3 — DS6 Python admission of the DS18 projection

The pre-repair four-node Vitest selector had two failures and two passes. The
read-only current-measurement node expected the dated `94/94` freeze but observed
the current `126/126`; the persistence node failed because Python still projected
primitive adoption from the DS1 readiness population as `unknown`. A direct
persistence invocation confirmed the owned failure as `health-metric rows do not
bind the recomputed canonical-source projection`.

Mechanism commit: `2d35c2e71` (`fix(atlas): admit live DS18 health projection`).

The Python admission adapter now invokes the canonical DS18 checker through the
repository `.venv/bin/python -I` with the fixed minimal child environment and the
resolved allowlisted Node 22 executable from `_trusted_node`. It admits exactly
five fields, requires `predicate_provenance: independently_reconciled`, positive
integer counts, and `covered_root_count == obligated_root_count`; it derives the
measured row without storing any current count in code. The row content-binds the
register, schema, checker, and AST scanner. Checker rejection, duplicate or
malformed JSON, extra fields, wrong provenance, boolean/non-positive counts, and
incomplete coverage all produce an exact bounded reason and retain
`unknown` / `not_established` with zero known facts. The shared source-projection
signature was updated for both health and readiness; the readiness reconciler's
five-value interface replayed successfully. An already-landed producer wording
change (`Six` to `Seven` source proxies) was mirrored in the owned Python adapter
because it otherwise independently blocked the persistence node.

GREEN receipts: the canonical fixed-environment checker exited 0 with 621
production files, 759 roots, and 126/126 covered obligated roots. Direct Core CAS
persistence exited 0 with a measured 126/126 primitive row, the same three current
facts, `predicate_provenance: recomputed`, and four DS18 basis refs. The exact
persistence Vitest node passed (`1 passed | 22 skipped`); the exact caller `PATH`
and `NODE_OPTIONS` nodes passed (`2 passed | 21 skipped`); Ruff, byte compilation,
and `git diff --check` passed. The final four-node selector had three passes and
one task-D-owned read-only failure: the current-measurement node still expects
`94/94` while the producer correctly emits `126/126`. No TypeScript source or test
was changed.

Pattern closeout: P03's hidden DS18 richness is now consumed by the existing
persistence bridge; P29/P32 are met by replay and content refs rather than marker
presence; P37 fails closed unless the checker itself establishes the independent
predicate; P38 measures the obligated-root relation rather than a stored count.
The owned Python predicate is green. The remaining task-D literal expectation is
the recorded P41 handoff, not a reason to substitute another frozen total.

#### Task 3 independent-review correction

Review found that commit `2d35c2e71` had changed the shared
`_health_source_projection()` helper from its established no-argument two-tuple
contract to a required-argument three-tuple. The exact readiness admission witness
failed with `TypeError: _health_source_projection() missing 1 required positional
argument: 'node_executable'`. Commit `5babf54d0` restores that interface exactly.
Readiness again consumes only the canonical health-source projection and does not
run DS18. The health path invokes DS18 separately and overlaps that independent
replay with the fixed TypeScript producer; their reports are still compared before
admission, so disagreement continues to reject rather than widen authority.

The same repair replaces unbounded checker capture with a selector-driven process
reader capped at 8 MiB independently for stdout and stderr, matching the producer's
`maxBuffer`. More than 8 MiB on either stream kills the checker and yields a
77-character bounded reason. Ordinary nonzero stderr is copied into a limitation
only through a 2,048-byte excerpt; a 3,000-byte witness produced a 2,151-character
reason with an explicit truncation suffix. Real-process witnesses for stdout
overflow, stderr overflow, bounded ordinary failure, and a small ordinary failure
all passed.

The earlier journal wording that zero-exit malformed checker output was proven to
persist as unknown is retracted. Python parses such output tolerantly at its helper
boundary, but the canonical TypeScript producer currently performs `JSON.parse`
and strict projection parsing without a tolerant catch; persistent zero-exit
malformed output therefore terminates the producer before Python can admit a row.
That behavior is task D's exact source handoff in
`runDs18TimeSemanticsCoverageValidator`: if persisted unknown is required for this
case, task D must convert JSON/schema parse rejection into the same bounded
`kind: not_established` result. Task G did not fabricate a producer report or edit
the task-D source.

The actual nonzero checker path was exercised end to end by temporarily changing
only the register's `covered_root_count` from 126 to 0, invoking the real producer
and persistence operation, and restoring the exact original bytes in `finally`.
Persistence exited 0 with `unknown / not_established`, zero known facts, and the
bounded limitation prefix
`ds18_time_semantics_count_drift:covered_root_count`. The restored register digest
was `c2893870139f3eae5042e54ba23a1692c10680f1ec0dc404cd3d879efe01544f`, and the
post-witness Git diff was empty for the register. The exact red-denominator Vitest
node separately passed the unknown-row schema contract.

Final focused receipts after the correction: the exact readiness witness passed
(`1 passed | 32 skipped`, 13.44 s); exact persistence plus red-denominator nodes
passed (`2 passed | 21 skipped`, 7.80 s); exact caller `PATH` and `NODE_OPTIONS`
nodes passed under the default 15-second ceiling (`2 passed | 21 skipped`,
12.96 s). The canonical checker remained 621 files / 759 roots / 126/126 at
`independently_reconciled`; Ruff, byte compilation, and `git diff --check` passed.
The separate task-D `94/94` current-measurement expectation remains the only known
focused read-only red.

#### Task 3 second-review P40 correction

The second review classified the 2,048-byte stderr excerpt as the same producer-
parity class one level deeper: TypeScript's `runDs18TimeSemanticsCoverageValidator`
uses the full trimmed stderr available inside its 8 MiB `maxBuffer`, while the
Python expected row discarded bytes within that producer domain. Per P40, commit
`9e0847482` widens the adapter once to the full quantity the producer contract
carries. For a nonzero checker result at or below 8 MiB per stream, Python now
decodes all stderr with UTF-8 replacement and applies `strip()`, exactly matching
the producer's replacement/trim semantics. The earlier statement that the
3,000-byte failure should end with a 2,048-byte truncation suffix is retracted.

The focused 3,000-byte RED witness produced a 2,151-character Python reason versus
the 3,070-character TypeScript-equivalent reason; reason equality and full
expected-row equality were both false. After `9e0847482`, the same witness produced
3,070 characters on both sides with both equalities true. A small nonzero checker
still produced exactly
`DS18 time-semantics coverage validator rejected the current tree (7): ordinary failure`.
The actual register-corruption replay again persisted `unknown / not_established`
with zero known facts and the exact
`ds18_time_semantics_count_drift:covered_root_count` limitation; the register was
restored to SHA-256
`c2893870139f3eae5042e54ba23a1692c10680f1ec0dc404cd3d879efe01544f` with no Git
diff.

P40 stopping ruling: this is the second same-class finding and the one permitted
widening now covers the producer's complete at-or-below-8-MiB stderr domain. Two
source-boundary handoffs remain explicit. First, checker output beyond the 8 MiB
`spawnSync.maxBuffer` in task-D-owned `runDs18TimeSemanticsCoverageValidator` is a
declared bounded residual; Python's own overflow reason is helper behavior, not an
end-to-end producer-parity claim. Second, zero-exit malformed stdout is parsed by
task-D-owned `JSON.parse` plus the strict DS18 schema before persistence and can
throw before Python receives a report. Closing either handoff requires task D to
emit a stable typed bounded result from the producer. There will be no third
adapter patch for either beyond-domain case.

Second-review focused receipts: persistence plus red-denominator passed (`2 passed
| 21 skipped`, 9.79 s); readiness passed without a DS18 scan (`1 passed | 32
skipped`, 20.58 s); caller `PATH` and `NODE_OPTIONS` isolation passed under the
default per-test 15-second ceiling (`2 passed | 21 skipped`, 18.42 s total; 17.51 s
combined test phase). Ruff, byte compilation, and `git diff --check` passed. No
TypeScript source or test changed; the task-D `94/94` expectation remains the known
focused read-only red.

#### Task 3 final P40 stop correction

Final re-review found a third instance of the same stderr-parity class, so P40's
stop rule applies and Task G makes no further adapter change. Python currently
normalizes decoded stderr with `str.strip()`, while the task-D TypeScript producer
uses ECMAScript `String.prototype.trim()`. Their Unicode whitespace sets differ:
Python strips U+001C where ECMAScript does not, and ECMAScript trims U+FEFF where
Python does not. General nonzero stderr parity is therefore **not established**,
even for output at or below 8 MiB. The 3,000-byte ASCII-`z` witness remains a
worked example only; its equal 3,070-character reasons and rows do not prove the
class.

Task G's closure evidence is narrowed to the exercised real failure path: changing
the DS18 register's `covered_root_count` from 126 to 0 made the canonical checker
return the ASCII `ds18_time_semantics_count_drift:covered_root_count` rejection,
and the real producer plus persistence adapter stored `primitive_adoption` as
`unknown / not_established` with zero known facts. That exact count-drift path is
established; arbitrary nonzero stderr normalization is not.

The declared task-D bounded residual now folds together all three producer/error
boundary cases: output beyond `spawnSync`'s 8 MiB `maxBuffer`, zero-exit malformed
stdout that throws before Python admission, and Unicode trim-set divergence on
nonzero stderr. The smallest capability that closes the residual is a
producer-owned, typed and bounded error-normalization contract consumed identically
by the TypeScript producer and Python admission. No such shared contract exists
here: the producer and adapter currently construct and normalize their rejection
strings independently, with no common typed error packet or normalizer. Per P40,
this third worked example triggers documentation of the limitation, not a third
Python patch.

#### Task 1 final review correction

Whole-branch review found the same scope-obligation-loss class one level deeper:
the manifest schema originally required three unique strings but did not pin the
three ratified IDs. A mutated manifest could replace `ds8-global-case-index`, and
a DS12 plan matching that rogue set left the gate green. The reviewer's exact
falsifier first failed with `errors == []`. Per P40, the mechanism was widened
once to the real invariant: the schema now admits only the three ratified row IDs,
while the existing length-three and uniqueness constraints require their complete
set. The same corrupted-manifest plus matching-plan falsifier now passes, and the
complete focused scope wave passes 7/7. No per-row checker branch was added.

## Register closure dossier

Arithmetic is exact and does not merge unlike states:

- core: `7 = 2 closed + 4 open + 1 blocked + 0 ambiguous`;
- adjacent: `4 = 1 closed + 1 open + 2 blocked + 0 ambiguous`;
- total: `11 = 3 closed + 5 open + 3 blocked + 0 ambiguous`.

### `ds4-waist-decision-grade`

**Verdict:** `open`.

**Predicate and exit:** the complete generated-family census reads the two
OpenAPI-derived families in `architecture/generated_artifacts.toml` and their six
outputs, then runs `rg -n '\bDecisionGrade\b'` over those outputs and
`schemas/runtime_api_v1.openapi.json`; it exits `1`, meaning zero named
`DecisionGrade` occurrences. The owner `Literal` still resolves in
`src/polisyos/pdc/_impl/layer2_readiness.py`, while the sole dashboard swap point
continues to accept `unknown` and emit `unrecognized`.

**Exact append-only register prose:**

> **TASK G CLOSURE RE-CENSUS 2026-08-31 — `open`.** The next-regeneration swap has not occurred. The complete registered generated denominator is two OpenAPI-derived families / six outputs — five `runtime-api-client` outputs and one dashboard API-types output — plus their source `schemas/runtime_api_v1.openapi.json`; a direct named-symbol scan finds zero `DecisionGrade` occurrences across that complete set. The real four-value owner `Literal` still exists in `pdc/_impl/layer2_readiness.py`, while the sole dashboard swap point still accepts `unknown` and presents every value as `unrecognized`. Capability state remains `surface_missing`; no client regeneration or generated file was changed here.

### `ds5-frontend-baseline-manifest-bindings-stale`

**Verdict:** `closed`.

**Predicate and exit:** a complete direct Python walk of
`lint.resolution_content_bindings` exits `0` after asserting 46 binding rows over
45 unique paths, a binding-row suffix denominator of 2 `.cjs` + 14 `.ts` + 30
`.tsx`, zero current SHA-256 mismatches, and all six paths changed by ancestor
`31f66448a` present and fresh. The same walk separately establishes that
`lint.resolutions[].origin_identity.source_content_sha256` remains present in
75/75 historical resolution rows.

**Exact append-only register prose:**

> **CLOSED 2026-08-31 — the stale-binding subject is absent on the canonical binding plane.** Ancestor `31f66448a` re-anchored the six named paths. A complete current walk of `lint.resolution_content_bindings`, the field consumed by `_resolution_content_binding_errors`, reports 46 binding rows over 45 unique paths — 2 `.cjs`, 14 `.ts`, and 30 `.tsx` binding rows — with zero SHA-256 mismatches; all six re-anchored paths are fresh. The older `lint.resolutions[].origin_identity.source_content_sha256` coordinate still exists in 75/75 resolution rows, but it is provenance for diagnostic origins, not the current content-binding field. This closes the stale-binding defect; it does not delete or reinterpret those 75 historical origin receipts.

### `ds5-waist-successors-routed-to-unscoped-slices`

**Verdict:** `blocked`.

**Predicate and exit:** the complete parser for the direct-`Badge` debt table in
`DS5-enforcement-waist.md` exits `0` after reproducing 27 groups / 58 sites and
the historical successor subset of 6 groups / 11 sites. The closure predicate
`planless_groups == 0 and planned_but_unabsorbed_groups == 0` exits `1`: DS12 and
DS14 still account for 4 planless groups / 8 sites, while DS15 and DS18 account
for 2 planned-but-unabsorbed groups / 3 sites.

**Exact append-only register prose:**

> **TASK G BASIS CORRECTION 2026-08-31 — `blocked`.** Re-parsing the complete DS5 direct-`Badge` debt table reproduces 27 groups / 58 sites. The six historical successor handoffs comprise 6 groups / 11 sites: DS12 has 3/7, DS14 1/1, DS15 1/1, and DS18 1/2. Exactly 4 groups / 8 sites remain routed to planless slices — DS12 3/7 and DS14 1/1 — not six groups. DS15's `promotion candidate status` 1/1 and DS18's `projection source freshness` 1/2 now target standalone plans, but neither exact group label is absorbed by its plan; they are planned-slice handoffs still unclaimed, not planless routes. Routing remains non-owning. Close only when DS12 and DS14 have standalone claiming plans and all six historical handoffs are explicitly absorbed into their respective slice scopes.

### `ds6-atlas-evidence-primitive-adoption-projection-stale`

**Verdict:** `closed` on the bounded predicate below.

**Predicate and exit:** the fixed-environment command below exits `0` and reports
621 production TypeScript files / 759 roots / 126 obligated roots / 126 covered
roots at `independently_reconciled`:

```bash
env -i HOME=/var/empty LANG=C LC_ALL=C PATH=/usr/bin:/bin TZ=UTC \
  POLISYOS_NODE_EXECUTABLE=/opt/homebrew/Cellar/node@22/22.22.2_1/bin/node \
  .venv/bin/python -I \
  architecture/atlas_surfaces/check_frontend_disposition_register.py \
  --check-ds18-time-semantics-coverage
```

Direct Core CAS persistence exits `0` with measured 126/126. The finally-guarded
real register corruption changing only
`covered_root_count: 126 -> 0` exits `0` after the real producer and persistence
store `unknown / not_established`, zero known facts, and limitation prefix
`ds18_time_semantics_count_drift:covered_root_count`; it restores the exact
register SHA-256
`c2893870139f3eae5042e54ba23a1692c10680f1ec0dc404cd3d879efe01544f`
and leaves no register diff. The exact readiness witness
`corepack pnpm exec vitest run src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts --testNamePattern='gates the zero-instance stable arm identically to implemented'`
exits `0` with 1 passed / 32 skipped. From `apps/runtime-dashboard`, the final
six-node health selector is:

```bash
corepack pnpm exec vitest run src/test/evidence/atlasHealthMetrics.test.ts \
  --testNamePattern='records the six current measurements and the seventh protocol seam honestly|drops primitive adoption to not established when its moving denominator is red|keeps every metric on the closed instrument without claiming independence|persists the producer-observed report and snapshot through Core CAS|ignores a caller PATH node that emits a schema-valid forged report|does not inherit caller NODE_OPTIONS into the fixed producer'
```

It exits `1` with 1 failed + 5 passed + 17 skipped; its sole failure is the
task-D-owned 94/94 expectation against live 126/126.

**Exact append-only register prose:**

> **CLOSED 2026-08-31 — the DS6 Python persistence edge consumes the live DS18 projection on its established bounded predicate.** The canonical replay establishes 621 production TypeScript files / 759 render-export roots / 126 obligated roots / 126 covered roots, and direct persistence admits measured 126/126 without storing a current count in Python. A finally-guarded real `covered_root_count: 126 -> 0` corruption made the canonical checker reject with ASCII `ds18_time_semantics_count_drift:covered_root_count`; the real producer plus persistence stored `unknown / not_established` with zero known facts, then restored the exact register bytes and SHA-256. Closure is deliberately no broader. Task D retains one bounded producer/error residual with three examples: output beyond its 8 MiB `spawnSync` buffer, zero-exit malformed output that can throw before Python admission, and Unicode `trim()` / `strip()` divergence on nonzero stderr. The smallest missing capability is one producer-owned typed and bounded error-normalization contract consumed identically by TypeScript and Python; no such shared contract exists here. Task D also retains the stale read-only expectation of 94/94 while the live producer emits 126/126. The dated 605/719/77/77 and 616/733/94/94 receipts remain historical freezes, not competing current totals.

### `ds8-global-case-index`

**Verdict:** `open`.

**Predicate and exit:** the exact command below exits `0` at 7/7:

```bash
uv run python -m unittest \
  architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_slice_scope_obligations_leave_unstarted_targets_open \
  architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_slice_scope_obligations_require_the_exact_unique_input_set \
  architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_slice_scope_obligations_accept_each_target_only_with_all_inputs \
  architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_slice_scope_obligation_manifest_cannot_replace_required_input \
  architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_slice_scope_obligations_reject_duplicate_target_plans \
  architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_slice_scope_obligations_read_tracked_slice_plans_without_filename_proxy \
  architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_validate_enforcement_consumes_live_scope_obligation_errors
```

`rg --files docs/plans/active/atlas-slices | rg '/DS(12|13|14)-'` exits `1`:
no standalone target plan exists. The manifest fixes acknowledgement at
`candidate_only` with `closure_effect: none`.

**Exact append-only register prose:**

> **SCOPE-SETTING GATE ADDED 2026-08-31 — still `open`.** `architecture/atlas_surfaces/slice-scope-obligations.json` makes `ds8-global-case-index` one of exactly three mandatory `atlas_residual_inputs` for every future DS12, DS13, or DS14 `type: slice-plan`; the schema pins the same three ratified IDs, and the live Atlas checker requires their exact unique set. It rejects manifest replacement, omissions, additions, duplicates, marker-only input, duplicate target plans, and filename-proxy enumeration. Acknowledgement is explicitly `candidate_only` with `closure_effect: none`. No standalone target plan currently exists, so no slice has claimed this obligation and this Atlas-side row does not close. The separate task-C producer half, `ds10-global-case-index-producer-allocation`, still lacks on this branch a canonical global-index producer/provider bridge and its named behavioral test; producer completion cannot close this scope half, and this scope mechanism cannot close the producer half.

### `ds8-local-reviewer-note-persistence`

**Verdict:** `open`.

**Predicate and exit:** the same seven exact scope-obligation nodes exit `0` at
7/7; the complete standalone DS12/DS13/DS14 plan enumeration exits `1` with no
matches. The manifest carries this exact row ID and has no closure authority.

**Exact append-only register prose:**

> **SCOPE-SETTING GATE ADDED 2026-08-31 — still `open`.** `architecture/atlas_surfaces/slice-scope-obligations.json` makes `ds8-local-reviewer-note-persistence` one of exactly three mandatory `atlas_residual_inputs` for every future DS12, DS13, or DS14 `type: slice-plan`. The live checker enforces the exact unique input set generically; acknowledgement remains `candidate_only` and has `closure_effect: none`. No standalone DS12, DS13, or DS14 plan exists, so this lane has made the obligation unmissable without pretending to own or close it. Closure requires a named slice to take reviewer-note persistence into its actual scope.

### `ds8-signed-public-decision-surface`

**Verdict:** `open`.

**Predicate and exit:** the same seven exact scope-obligation nodes exit `0` at
7/7; standalone target-plan enumeration exits `1`. On this branch `rg` for
`test_public_decision_projection_is_custody_bound` exits `2` because the named
`tests/unit/runtime/http/test_public_export.py` artifact is absent.

**Exact append-only register prose:**

> **SCOPE-SETTING GATE ADDED 2026-08-31 — still `open`.** `architecture/atlas_surfaces/slice-scope-obligations.json` makes `ds8-signed-public-decision-surface` one of exactly three mandatory `atlas_residual_inputs` for every future DS12, DS13, or DS14 `type: slice-plan`; exact-set enforcement is live, candidate-only, and explicitly non-closing. No standalone target plan currently exists, so this Atlas-side scope obligation remains `absent/unallocated`. The separate task-C half, `ds10-public-decision-rendering`, still lacks on this branch the custody-bound public producer/rendering chain and its named `test_public_decision_projection_is_custody_bound` artifact. Neither half closes the other.

### `scenario-composer-dark-theme-visual-instability`

**Verdict:** `open`.

**Predicate and exit:** a complete byte walk over all 125 tracked
`docs/plans/**/*.md` files finds four carried-prose hits and no explicit team
assignment satisfying the row. The closure predicate `assigned team + declared
reproduction ceiling + repair or bounded residual with falsifier` exits `1`.

**Exact append-only register prose:**

> **TASK G CLOSURE RE-CENSUS 2026-08-31 — `open`.** This is an ordinary frontend-team allocation, not an institutional appointment. The complete 125-file tracked plan-Markdown corpus contains four carried-prose hits but still no explicit team assignment for the scenario-composer dark-theme visual instability, and no declared-ceiling reproduction, repair, or bounded-residual falsifier has been supplied. Task G does not allocate it by naming a likely team. Close only after an ordinary owner assignment and the existing reproduce-then-repair-or-bound predicate is executed.

### `atlas-python-governance-workload-identity-drift`

**Verdict:** `closed`.

**Predicate and exit:** `uv run --extra test --with 'jsonschema>=4.25' python -m
pytest tests/repo_quality/tools/test_timing.py::test_atlas_python_governance_lane_names_one_exact_runnable_workload`
exits `0`, selecting and passing 1/1 test. It runtime-collects the exact historical
path-to-node mapping from publication revision
`6bcc95bff32645189ff2ed65a719c7990e48c52a`.

**Exact append-only register prose:**

> **CLOSED 2026-08-31 — the receipt is bound to its exact historical runnable map, not a moving total.** At publication revision `6bcc95bff32645189ff2ed65a719c7990e48c52a`, isolated real pytest collection of the two catalog paths yields exactly 30 + 37 = 67 ordered node IDs. The raw test blobs bind to SHA-256 `841466263c618a3142a6d5327c72072ad0e95bf4d738516f6d240eb98601b685` and `7f5418b7e809b1f1bac0470ecc2a553c878b14d886ea39494362067908e7ca0f`; canonical compact JSON of the complete ordered map binds to `9b08f0ed2e74bf888009820529e2901c6dd3bedb40bf55a679a362efaf12aea6`. The exact selector passes because the published `67 tests passed` receipt matches that Git-bound path-to-node mapping. Recorded `181`, `190`, `210`, current helper-derived `191 + 41 = 232`, and current pytest-collected `194 + 41 = 235` remain distinct named derivations; none is selected as a replacement for the historical sample. This supersedes the earlier instruction to rewrite the receipt toward `210`, which was the same moving-count proxy defect.

### `ds8-lex-clerk-authority-repair`

**Verdict:** `blocked`.

**Predicate and exit:** `test -f
docs/plans/active/atlas-slices/DS10-capability-discovery.md` exits `0`; that plan
explicitly splits Lex route/discovery from pipeline mutation. `rg --files
docs/plans/active/atlas-slices | rg '/DS14-'` exits `1`. The master DS14 detail
names `features/clerk` as a strangle target but is not a standalone claiming plan.

**Exact append-only register prose:**

> **TASK G ADJUDICATION 2026-08-31 — `blocked`.** The Atlas table's description of DS10 as Capability Discovery is correct. The wrong statement is DS8's unqualified `Lex → DS10` routing when read as a whole-authority transfer: the implemented DS10 plan keeps Lex route/chrome and legal-norm discovery integration with `team-design`/DS10, while Lex pipeline mutation remains a fixed authenticated operation owned by `team-lex`. Thus the discovery subset of the shorthand is valid, but the undifferentiated routing is not. Clerk remains blocked: the Atlas master gives DS14 a substantive bounded-agent scope and names `features/clerk` as its candidate strangle target, but no standalone DS14 slice plan has taken that obligation into scope. Architect edit required in the Atlas master: record the split as `Lex route/discovery → DS10/team-design; Lex pipeline mutation → team-lex; Clerk/features-clerk → DS14 only when a standalone DS14 plan claims it`. This lane does not make that architect-only edit.

### `ds8-public-case-publication`

**Verdict:** `blocked`.

**Predicate and exit:** `rg --files docs/plans/active/atlas-slices | rg '/DS12-'`
exits `1`. The master contains a substantive DS12 Public Publication Foundation
roadmap section, but no standalone `type: slice-plan` claims this row. The new
scope manifest's complete three-row input set does not contain this row ID.

**Exact append-only register prose:**

> **TASK G CLOSURE RE-CENSUS 2026-08-31 — `blocked`.** The Atlas master's substantive DS12 Public Publication Foundation section corrects the historical claim that DS12 was only a one-line idea: it defines the signing/verification chain, public record and certificate endpoints, typed-empty promoted-record slot, public MACHINE twin, and forged-packet negative. It is still an architect roadmap section, not a standalone claiming DS12 slice plan. Routing this row to DS12 therefore remains candidate routing, not ownership. The new three-row scope-obligation mechanism intentionally does not cover `ds8-public-case-publication`. Close this routing residual only when a standalone DS12 slice plan explicitly takes public case publication into scope and the obligation is superseded into that plan.

### Cross-row mechanism, handoffs, and out-of-scope findings

The scope-forcing mechanism covers exactly
`ds8-global-case-index`, `ds8-local-reviewer-note-persistence`, and
`ds8-signed-public-decision-surface`, independently for each future DS12, DS13,
and DS14 standalone plan: three obligation rows by three target slices. It does
not cover `ds8-public-case-publication`, appoint an owner, prove implementation,
or close a row. Its schema pins the three ratified residual IDs; the focused
corruption probe proves that a rogue manifest and a matching plan cannot jointly
replace one while leaving the gate green.

Task C's global-case producer half still needs the canonical index/store producer,
provider bridge, and
`test_case_provider_is_backed_by_canonical_global_index`; the named test is absent
on this branch. Its public-decision half still needs the custody-bound public
producer/rendering chain and `test_public_decision_projection_is_custody_bound`;
the named test artifact is absent on this branch. These producer halves neither
close nor are closed by the Atlas scope halves.

Task D retains the stale health-metric expectation of 94/94 against live 126/126
and the single bounded producer/error residual recorded in the DS6 block. Task G
did not edit TypeScript source or tests.

The full live Atlas enforcement command, `uv run python
architecture/atlas_surfaces/check_atlas_enforcement.py --check`, exits `1` on
current authority, inventory, source-denominator, query-cache, status, and
architecture-graph findings; it emits no `slice_scope_obligation_*` error. No
exact pre-Task-G base replay establishes those findings as inherited, so their
provenance remains `not_established`. Architecture guardrails, `uv run
polisyos-tools architecture guardrails check`, also exit `1` on
`trust-claim-posture-register` generated-probe validation; its provenance is
likewise not established as inherited and it is outside this lane.

The requested bound debt-ledger gate is not green. `PYTHONPATH=.:src
.venv/bin/python tools/quality/validation/check_debt_ledger.py --check` exits
`1`, reporting 151 register IDs, 18
`closure_signal_identity_unresolvable` findings, and 18 matching
`closure_signal_count_exit_disagreement` findings. P41 was applied to that
specific class, not to the command's whole output: an exact replay from this
slice's base `784d02014` in a detached shared clone, using the same bound
interpreter and `PYTHONPATH=.:src`, also exits `1` with the same 151 / 18 / 18
measure. A complete static walk derives those 18 identities from 15 target test
paths; intersecting that full target-path set with all eight Task-G changed paths
exits `0` at an empty intersection. The 18-identity red is therefore inherited
and disjoint from Task G. The base replay also has additional historical
topology/render findings, so no broader claim of byte-identical or wholly
inherited debt-ledger output is made. The register already assigns this exact
class to open row `debt-closure-signals-name-unwritten-tests`; repairing the
architect-owned checker or register is outside this lane.

The Atlas master overview and DAG still describe DS14 as gated on the Phase-6
O-block, while the detailed DS14 section explicitly supersedes that as misnamed
and states the real gate as GY-I plus DS9. Correcting that internal master-plan
inconsistency is architect-only. DS15's `promotion candidate status` 1/1 and
DS18's `projection source freshness` 1/2 remain planned-slice handoffs not
absorbed by their plans. The known task-B 118-versus-117 denominator red and the
missing-`rdflib` collection error were outside this lane's changed denominator and
were not used as closure evidence.
