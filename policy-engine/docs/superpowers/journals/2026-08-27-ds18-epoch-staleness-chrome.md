# DS18 epoch and staleness chrome — execution journal

## Execution identity and boundary

- Attached branch: `codex/ds18-epoch-staleness-chrome`.
- Execution base: `a38ff50a505f0d53f52a32eac220a5644483bcfb`.
- Amended plan carried forward by append-only merge commit `1b78d1a12`.
- Product-root coordinate: `git rev-parse --show-prefix` returned `policy-engine/`.
- C00 changed only the plan and this P39 journal companion: **0 mechanism paths**.
- Declared mechanisms / hard ceiling after the C00 generator probe: **40 / 44**;
  widening rounds: **1 / 7**.
- DS11 landing `4ff11db52` is already an ancestor of the execution base. WAIT-DS11
  is satisfied at entry; no inward DS11 source-sync merge remains.

## C00 census — two independent derivations

| Fact | Derivation A | Derivation B | Admitted result |
| --- | --- | --- | --- |
| GY-N12 commits / paths | `rev-list --count`; `diff --name-only` record count | formatted log record count; diff shortstat denominator | `24 / 174 = 24 / 174` |
| Python source denominator | complete `Path.rglob('*.py')` walk | full `HEAD` tree filter | `2,598 = 2,598`; symmetric difference zero |
| direct route files / HTTP operations | AST over direct `routes/*.py`, including `__init__.py` | anchored decorator census over the same direct-file set | `17 / 105 = 17 / 105`; excluding only zero-operation `__init__.py` is `16 / 105` |
| WebSocket operations | AST decorator classification | anchored WebSocket decorator census | `1 = 1`, outside the HTTP/OpenAPI denominator |
| visible HTTP operations | AST excludes `include_in_schema=False` | `105 - 2` from exact hidden SSE decorators | `103 = 103`; hidden routes are `runs.py:799` and `:1145` |
| frozen OpenAPI paths / HTTP operations | Node structured walk | independent Python JSON walk | `101 / 103 = 101 / 103` |
| source/OpenAPI drift | exact method/path symmetric difference | reverse exact method/path symmetric difference | empty / empty: drift **zero** |
| registered generated family | generated-artifact TOML parse | exact tracked-path membership | six generated clients/types plus schema = **seven** |
| DS4 production call sites | complete `rg` identifier walk | complete `git grep` identifier walk | `0 = 0` after identical production exclusions |
| DS5 lower bound | JSON resolution walk | independent JSON traversal | `21` decision-bearing rows / `10` unique paths in both derivations |
| DS11 landed path set | `f935e0c2e..8b9b47309` branch contribution | `2525da730..4ff11db52` landing first-parent delta | `65 = 65`; symmetric difference zero |

The route-file inclusion rule is literal: every direct Python module matched by
`src/polisyos/runtime/http/routes/*.py`, including `__init__.py`. The initializer has
zero operations; excluding it must be reported as 16 files, never silently substituted
for the declared 17-file denominator.

The DS11 landed set is planning live 64 plus
`apps/runtime-dashboard/e2e/a11y/routes.a11y.spec.ts`, with no removal. The planning
63-tracked/64-live values and Python 2,600 denominator remain historical only.

## Closed drift and capability decomposition

`POST /api/v1/control/decision-validity/epoch-batches` is live at
`src/polisyos/runtime/http/routes/control.py:521-535` and is present in the frozen
schema. That satisfies the epoch-batch source→OpenAPI part of DS18-CC05 at entry.
CC05 still requires the new epoch-staleness GET and semantic propagation of both
operations through every registered output.

The seven-output readback does not support one aggregate capability label:

- schema, package `types.ts`, and dashboard `types.ts`: operation/path and DTO artifacts
  implemented;
- package `runtimeApiClient.ts` and `canonicalRuntimeApiClient.ts`: DTOs present but no
  executable epoch-batch method;
- both JavaScript wrappers: no executable epoch-batch method;
- canonical executable-generator selection: `bridge_missing`;
- executable generated operation: `consumer_missing`;
- operation-set completeness: `semantic_test_missing`; the existing freshness check
  correctly reproduces the omission and therefore cannot establish this property.

Therefore the planning aggregate `bridge_missing` label is stale, but a narrower
generator `bridge_missing` finding remains. C03 has no epoch-batch schema catch-up left:
it repairs the generator selection, adds/regenerates the new GET, propagates executable
package operations, and proves the existing POST. C04 refreshes the dashboard member
and closes the seven-output receipt atomically under the generator seam.

An independent C00 probe parsed the generator's POST selection through both Python AST
and the imported runtime constant; the sets agreed and both omitted
`admit_epoch_validity_batch`. A structured schema walk found the operation, in-memory
sanctioned rendering still omitted it, and a complete four-client readback found no
executable method. The probe exited 0; uptime load `3.11 3.14 3.33` →
`3.11 3.14 3.33`; `real/user/sys/user+sys = 0.07/0.05/0.01/0.06 s`.

This is bucketed **NEW: generator semantic selection/completeness**, not the same
source→schema drift class one level deeper. C03 therefore declares
`tools/ops_runners/runtime/generate_runtime_client.py`, spends widening seam 6 and the
named HTTP/ABI reserve path: **39 → 40** mechanisms, ceiling unchanged at **44**, rounds
**0 → 1 of 7**. A stable 39 would now be a proxy for the plan rather than the property.

## DS11 entry receipt and exact-byte inheritance

- The two landed-set commands returned 65 paths with zero symmetric difference:
  `real/user/sys/user+sys = 0.01/0.00/0.00/0.00 s` and
  `0.02/0.00/0.00/0.00 s`.
- The C04-C06 fence has 22 existing owners and five planned additions; no frontend
  owner moved, so that fence spends no widening round. The separate generator finding
  above spends the only round at C00.
- `pnpm-lock.yaml` is unchanged across the DS11 landing range.
- Landed `loadPosture.ts:47-50` captures and copies `arrayBuffer()` bytes before fatal
  decode (`:58-63`), JSON parse (`:65-70`), and strict admission (`:71-74`). DS18's
  MACHINE loader must inherit this order and download the captured bytes, never a
  reserialization.

## Tooling and baseline receipts

| Command | Uptime before → after | `real` | `user` | `sys` | `user + sys` | Result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `corepack pnpm install --frozen-lockfile` | `4.25 3.90 3.47` → `5.97 4.30 3.63` | `12.93 s` | `6.10 s` | `22.92 s` | `29.02 s` | exit 0; landed lockfile accepted; no tracked mutation |
| focused backend entry baseline | `5.31 5.14 4.22` → `4.84 5.09 4.28` | `75.23 s` | `65.45 s` | `4.63 s` | `70.08 s` | exit 0; 39 tests |
| existing DS4/chart frontend baseline | `4.55 5.00 4.27` → `4.40 4.95 4.26` | `9.23 s` | `5.08 s` | `0.96 s` | `6.04 s` | exit 0; two files / seven tests |
| four-state C00 semantic falsifier | `2.29 3.57 3.86` → `2.29 3.57 3.86` | `1.53 s` | `1.65 s` | `0.24 s` | `1.89 s` | intended exit 1; all four behavioral assertions red |
| C00 plan/journal invariant readback | `5.88 3.89 3.38` → `5.88 3.89 3.38` | `0.10 s` | `0.05 s` | `0.12 s` | `0.17 s` | exit 0; two paths, 40 mechanisms, 44 ceiling, 1/7 rounds, both lane releases recorded, diff check clean |

The backend command covered temporal API, epoch validity cascade, monitors, and
lifecycle bridge tests. Its anchored collection count is 39, so the earlier 61-test
estimate and derived 214-second ceiling are rejected. The admitted focused ceiling is
143 seconds, derived only after the 75.23-second observation.

The first `uv sync --frozen --offline --extra lint --extra test --extra runtime --extra
ml` attempt exited 1 because the local cache lacks `jaxlib==0.8.2`. Its observed
`real/user/sys = 0.22/0.06/0.03 s` is a tooling **non-receipt** because the enclosing
uptime pair was not retained; no product finding or ceiling is derived from it. The
read-only integration environment was admitted only after current/integration/plan
`uv.lock` digests all matched
`3f9dfe227ec3c49747027fefa5d73acba9c9e21ec691c44829fb1066a69b38d1`,
and a `PYTHONPATH=$PWD/src` probe resolved `polisyos` to this execution worktree.

An initial falsifier placed outside the dashboard Vitest root was not discovered and
exited 1; that is a tooling non-receipt. The replacement ignored scratch test at
`apps/runtime-dashboard/.tmp/ds18-c00-temporal-falsifiers.test.tsx` imports the real
`TimeSemanticsLabel`, holds its shell constant, and mutates the underlying epoch,
institutional refusal, and replay-boundary state. It produced four intended failures:
stale/current divergence was invisible; the signer refusal did not render **Authority
not appointed**; epoch/current context was absent beside `as_of`; and a cross-epoch
replay remained unsegmented.

Three documentation-check harness attempts were rejected before the admitted row
above: the first omitted the new untracked journal from its changed-path query; the
next two tested the epoch route's path literal on decorator line 521 even though the
verified `521-535` range places that literal on line 522. Their failures were harness
findings, not plan findings; the corrected check verifies the decorator, literal and
handler range separately.

## Live lane serialization

Two independent sources — local declared-set intersection and the DS15 owner readback —
agree on the exact four-path active DS15 C02 overlap:

- `src/polisyos/core/contracts/control.py`;
- `src/polisyos/runtime/http/dependencies.py`;
- `src/polisyos/runtime/http/openapi_contract.py`;
- `src/polisyos/runtime/http/services/control/run_lifecycle.py`.

DS15 released attached, clean source-freeze coordinate
`b633ea7b75af4d07feaf0690926712353022d21f` (parent
`26d9c8f3b15b3bb60343f2eb1b33219b9bccfb5d`). The parent diff and an independent
`diff-tree` walk each return 30 paths with symmetric difference zero; all four overlap
mechanisms are present and the seven generated outputs intersect at zero. The receipt
ran at uptime load `2.42 2.61 3.00` → `2.42 2.61 3.00`;
`real/user/sys/user+sys = 0.07/0.03/0.02/0.05 s`. C01-C04 remain held only until this
exact append-only source input is integrated or lands on main and is read back; a
detached commit coordinate alone does not settle the execution branch. The earlier
zero-intersection planning observation is stale and is not reconciled away.

DS15 reports no current generator lock and all seven generated outputs clean, but it
will acquire the seam after its C02 source freeze. DS18 must re-derive the intersection
and coordinate immediately before C03's regeneration receipt and again before C04's
dashboard regeneration. GY-O0 released the
`src/polisyos/runtime/quality/README.md` companion at attached, clean readback
`e5d1c3ab7ffc2c4da00d26eb395d6f4c287175fd`; its last README edit is committed at
`08332b724`. DS18's companion is ordered after that state; a later GY-O0 resumption
will merge the then-current owner forward.

## C00 rulings and next boundary

- **Ruling:** decompose epoch-batch capability by layer. Reason: exact schema/type and
  executable-client inventories disagree with the old aggregate label. Cost if wrong:
  C03 could overclaim finished schema work or miss an absent consumer.
- **Ruling:** hold C01-C04 behind DS15's four-path release. Reason: the live measured
  intersection supersedes the historical zero. Cost if wrong: parallel overwrite at a
  contract/DI/service boundary.
- **Ruling:** use the lock-identical integration environment read-only with explicit
  execution-worktree `PYTHONPATH`. Reason: offline provisioning failed before tests.
  Cost if wrong: environment drift; the lock digest and module-path probes bound it.
- **Ruling:** WAIT-DS11 is closed at entry. Reason: the post-landing execution base,
  two 65-path derivations, landed loader readback, frozen install, and unchanged owner
  fence satisfy every condition. Cost if wrong: frontend work could inherit an
  unlanded owner; ancestor and set receipts prevent that.

Next boundary: preserve the clean attached branch with the C00 documentation receipt,
then integrate or consume from main the exact DS15 C02 source-freeze coordinate before
resuming C01. Mechanism budget is **40 / 44** and rounds are **1 / 7**.

## Sequencing correction and abort receipt

The former next-boundary wording above is historical and too broad: a sibling lane's
unlanded feature commit is not an integration source. `git cherry-pick -x b633ea7b...`
partially applied DS15's 30-path C02 checkpoint and exposed two conflicts in DS15-owned
documentation/test evidence. It would also have imported unrelated DS15 mechanisms,
including a Rego file predating the integration branch's authorization-parity repair.
No DS18 work was uncommitted: C00 was already frozen at `f4520cdb7`.

With explicit owner authorization, `git cherry-pick --abort` exited 0. Immediate
readback returned attached branch `codex/ds18-epoch-staleness-chrome`, HEAD
`f4520cdb76bd0f7ed4b9eeb8b80de67af72dc9ae`, and a clean status. No committed history
was rewritten and no DS15 path remains in the worktree or index.

The corrected lane census uses merge base
`f3e3d996bd6710e26f24fd913d4fe0547f1d1a0d` rather than a two-dot comparison against
`main`. A net tree diff and an independent full tree-object comparison each derive
**49** current DS15 contribution paths with symmetric difference zero. A regular-expression
Markdown-table parser and an independent row parser each derive **40** DS18 mechanisms;
both intersections contain exactly:

- `src/polisyos/core/contracts/control.py` (C01);
- `src/polisyos/runtime/http/dependencies.py` (C02);
- `src/polisyos/runtime/http/openapi_contract.py` (C02);
- `src/polisyos/runtime/http/services/control/run_lifecycle.py` (C02).

The seven-output set was independently recovered from the generated-artifact register
and exact registered-path membership; both current DS15 contribution derivations
intersect it at zero. DS15 is not yet an ancestor of current `main`; the integration
branch is at `f17c48555`, whose Rego parity repair is an ancestor of itself. DS18 waits
for DS15 to land on `main`, then merges `main` forward append-only and re-derives the
four-path release. It does not import another feature branch.

C01 has six currently uncontended mechanisms, but its seventh path is the canonical
`DecisionValidityEventRequest`/response owner. The cluster requires the mutually
exclusive, content-bound `monitor_event_ref` intake arm and bridge refs, so the six
paths cannot establish C01's full property without that contract. C01 is held whole;
C02-C04 may receive read-only red-test design but no mechanism execution before the
integration landing.

GY-O0 resumed C04 at clean attached `e5d1c3ab7` and again holds
`src/polisyos/runtime/quality/README.md`. DS18 will not edit that companion until GY-O0
returns its exact clean attached C04 release coordinate.

## C05 inherited-DOM preflight widening

A read-only downstream fence review found a live decision-bearing browser-PDF surface
outside the 40-path declaration. The first derivation follows the executable call graph:
`exportBureaucraticPdf` selects the live document DOM, `triggerPrint` preserves that
subtree, `BaseBureaucraticRenderer` supplies the article, and `BureaucraticHeader`
renders packet id/hash, render time and status without any admitted epoch/nonreceipt
node. The second derivation enumerates every `BureaucraticHeader` use and every
`BaseBureaucraticRenderer` wrapper: the single shared header serves all four live
bureaucratic renderers, and no sibling header node supplies temporal semantics.

Therefore changing only the already-declared AST and standalone HTML exporter cannot
make the browser-print/PDF path preserve a temporal node. This is bucketed **NEW:
decision-bearing inherited-DOM surface owner**. The smallest property-level mechanism
is
`apps/runtime-dashboard/src/features/artifacts/bureaucratic/renderers/shared/BureaucraticHeader.tsx`;
the shared print utility remains an unchanged inherited-DOM consumer.

The C01 owner map independently proved that its complete contract/producer/projection
property fits the seven declared mechanisms with no additional owner path. One of its
two backend reserve slots is therefore reallocated to the measured C05 owner: C01's
hard ceiling moves `9 → 8`, C05's declaration/ceiling moves `19/19 → 20/20`, and the
global declaration moves **40 → 41** while the hard ceiling remains **44**. A cluster
sum and an independent table-union parser both derive 41 unique mechanisms. Widening
seam 5 is spent; the current round receipt is **2 / 7**.

## C01 independent red review while held

The read-only owner review found two pre-existing P05/P32 authority leaks that C01's
behavioral red must preserve before repair. First,
`lifecycle_bridge._transition_for_event(...)` currently converts unbound metadata,
reason text and incident severity into lifecycle dispositions. Second,
`bridge_governance_events_to_claim_lifecycle(...)` accepts parallel event objects and
event refs without resolving and binding each pair, so reordered or substituted refs
can carry a shaped object. C01 must strangle both behaviors: source class, advisory
posture and owner disposition remain three independent dimensions, and only a
profile-verified persisted event handle may cross the bridge.

The review also sharpened the P37 boundary. Dependency/adjudication hashes establish
integrity but do not independently establish denominator completeness; a caller can
delete an edge and recompute every internal hash. The projection therefore renders a
typed `not_established` predicate unless an actual owner/verifier independently
reconciles the denominator and resolves owner-evidence bytes. Fixture-only positive
composition must not be promoted to production authority.

The unchanged incident producer remains outside the C01 mechanism set. No widening is
required: `monitors.py` will resolve the content-bound `IncidentReport`, invoke the
existing `incident_monitor_event(...)`, compare its exact incident/packet binding, and
then persist the strict incident arm. Directly trusting a caller-shaped incident id or
ref would instead require the undeclared producer path and is forbidden. Thus the
seven-path C01 fence and the global **41 / 44**, **2 / 7** budget remain unchanged.

Named red-first additions are: every legacy authority field is forbidden on the
monitor-ref arm; all six source classes round-trip distinctly under an identical
advisory posture; wrong-profile/hash/swapped bytes fail; event/ref reorder fails;
metadata/reason aliases cannot emit invalidate/reissue/supersede/withdraw; an appeal
cannot expand beyond its instance without owner scope evidence; every
source→evidence-line→claim→publication edge is required; recomputed incomplete
denominators fail; owner disposition evidence must resolve; and server `observed_at`
cannot become owner `as_of` or enter semantic identity.

## Execution hold withdrawal and C01 closure

The architecture owner withdrew every cross-lane hold before implementation. The
historical serialization receipts above remain an audit of why no source changed in
the prior session, but they no longer govern execution. DS18 does not inspect or wait
on sibling state, imports no sibling commit, edits all declared paths, and treats a
registered generated family as deterministic rebuild output. An append-only merge of
`main` at `f17c48555` produced branch merge commit `f6b1f18cf`; its sole content delta
was the already-landed Rego parity repair.

C01 changed all seven declared mechanisms and the nearest-owner README companion. Its
behavioral red receipts were:

- five failures when unbound metadata aliases could emit owner lifecycle dispositions
  and swappable event/ref lists could bind a shaped event to another ref;
- two control-contract failures before the mutually exclusive `monitor_event_ref` arm
  and all-or-none bridge receipts existed;
- collection failure before the epoch-staleness compiler existed; and
- the positive dependency fixture failed when a graph-integrity digest was substituted
  for the independently reconciled dependency-denominator receipt.

The green implementation now persists and exact-reads one strict six-class monitor
event, resolves its ref inside the lifecycle bridge, rejects authority-looking
metadata/free text, and preserves source class separately from advisory posture and
owner disposition. Correction/retraction use an exact source → evidence-line → claim
→ publication event. Appeals are instance-scoped while the other five classes may
traverse the independently reconciled dependency graph. The projection compiler keeps
server `observed_at` outside its semantic hash, exposes boundary lineage, freezes
limited/unestablished OpenWorldRisk, and rejects fake completed recompute status.

The two absence types are different strict DTOs. Exact signer nonreceipts produce
**Authority not appointed**, institutional closure wording, and
`appointment_is_closure_precondition=false`. The derived recompute gap produces
**Engineering capability not wired**, `producer_missing + bridge_missing`, and names
`polisyos.runtime.quality.derived_observations`; it cannot inherit institutional copy.

The first combined verification wave found one fixture topology error and one legacy
empty-collection compatibility regression. Both are same-cluster test/compatibility
findings, not new mechanisms. The admitted rerun covered 56 focused tests and exited 0:
uptime `3.78 3.78 3.70` → `4.02 3.86 3.74`;
`real/user/sys/user+sys = 98.94/93.64/4.12/97.76 s`, under the declared 180-second
wall ceiling. Changed-path Ruff exited 0. The full C01 path fence remains seven
mechanisms; global budget remains **41 / 44**, with **2 / 7** widening rounds spent.

## C02 live bridge, temporal route, and authorization closure

C02 began from behavioral failures, not route markers. `TemporalService` rejected the
real artifact/epoch/signer owner composition; the new monitor-ref request arm fell into
the legacy parallel-input path; and an executable owned-run request proved the new
authorization resource kind had no canonical resolver. The latter held the route,
permission and resource markers constant while changing the requested run tenant, so a
tenant-collection binding or borrowed resource kind could not satisfy the property.

The live control POST now resolves the exact persisted monitor bytes, requires a typed
perturbation plus `observed_epoch_ref`, exact-reads the packet→claim-ledger chain,
persists and reloads the canonical lifecycle result, derives and persists the epoch
advisory, and only then records the generic Decision Validity trigger. Callers cannot
supply class, target or disposition beside the ref. The monitor→advisory bridge is
behaviorally pinned for incident, appeal, correction, retraction, legal change and
discovered bias; each keeps its source class and distinct action, and appeal alone is
instance-scoped.

The temporal GET is directly `RUNS_REVIEW`-authorized through an exact owned-run
resolver, composes the real unallocated epoch predicate policy and transition-signing
authority, and returns their typed refusals as `200`. The same payload keeps inspection,
replay and MACHINE capabilities present. Institutional rows remain **Authority not
appointed** with `appointment_is_closure_precondition=false`; the derived-recompute row
remains **Engineering capability not wired** and names
`polisyos.runtime.quality.derived_observations`. A malformed owner artifact receives a
typed `422`, while server `observed_at` changes neither owner `as_of` nor semantic/replay
identity.

The positive fixture-only and real production-absence OpenAPI examples both validate
strictly. The whole runtime OpenAPI validator intentionally remains red before C03 on
the already-known property
`POST /api/v1/control/decision-validity/epoch-batches: missing 2xx success response
example`; the new GET example test was green in that same run. This is C03's preserved
red, not a C02 regression.

The owned-path resolver is a measured **NEW: owned-run authorization binding** class.
A complete resolver-table read and the independent executable request trace both name
`src/polisyos/runtime/http/resource_binding.py` as the smallest owner. The plan-table
regex census and an independent split-row parser each derive 42 unique mechanisms with
empty symmetric difference and identical cluster distribution
`C01=7, C02=6, C03=1, C04=3, C05=20, C06=5`. The budget is therefore **42 / 44** and
**3 / 7** widening rounds; the ceiling did not move.

Admitted verification receipts:

| Command | Uptime before → after | `real` | `user` | `sys` | `user + sys` | Result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| epoch-staleness route behaviors | `3.85 3.36 3.39` → `5.00 3.84 3.57` | `91.26 s` | `78.58 s` | `5.20 s` | `83.78 s` | exit 0; service dispatch, absences, role/tenant binding, malformed artifact, replay, time-role separation |
| live monitor POST exact-ref behaviors | `4.70 3.81 3.56` → `5.33 4.26 3.77` | `102.27 s` | `84.61 s` | `5.81 s` | `90.42 s` | exit 0; exact lifecycle/advisory persistence and pre-persist missing-epoch rejection |
| C01/C02 focused blast radius | `3.52 4.25 3.89` → `3.11 4.01 3.82` | `50.58 s` | `45.94 s` | `4.01 s` | `49.95 s` | exit 0; cascade, projection, monitor, lifecycle, invalidation, drift smoke, temporal and Decision Validity HTTP |
| architecture guardrails with venv on `PATH` | `2.34 3.33 3.56` → `3.78 3.54 3.62` | `64.81 s` | `58.44 s` | `8.43 s` | `66.87 s` | exit 0; all registered freshness probes and architecture checks passed |

Changed-path Ruff and `git diff --check` both exited 0. The first guardrail attempt
reached both runtime generated-family freshness checks, then exited 1 because its
trust-posture subprocess could not resolve the bare `python` executable; it is a tooling
non-receipt. Replaying with the lock-identical venv bin on `PATH` produced the admitted
green receipt above. Earlier combined-test ceiling, incomplete fixture-provider,
wrong-`PYTHONPATH`, and displaced test-helper-return failures were likewise harness
non-receipts and produced no product finding.

## C03 generated schema and executable package-client closure

C03 preserved the route/schema/type markers and exercised the generated clients. Its
first behavioral run exited 1 for the intended missing properties: the frozen POST had
operation id `admit_epoch_validity_batch`, but invoking
`admitEpochValidityBatch` raised `TypeError`; the live epoch-staleness GET was absent
from the frozen snapshot. The run took `real/user/sys = 34.12/30.16/1.96 s`.

The canonical generator now selects `admit_epoch_validity_batch`. The frozen OpenAPI
was regenerated from the live app and gained the epoch-staleness GET plus a strict,
owner-derived completed epoch-batch response example. Canonical package generation
then emitted executable `admitEpochValidityBatch` and `getRunEpochStaleness` methods in
both TypeScript and JavaScript wrappers. A register parse and an independent changed-
family path census each returned the same six C03 generated outputs — one schema and
five package outputs — with empty symmetric difference. No file outside those
registered outputs was produced by either generator.

The semantic gate is behavioral as well as fresh. A scratch copy retained the complete
schema shape and marker strings but changed nested
`InstitutionalAuthorityAbsenceView.title.const` from **Authority not appointed** to a
generic error; the real runtime contract checker exited 1 on drift. The admitted
nine-test C03 wave covered that falsifier, executable POST and GET calls, strict batch
example, whole OpenAPI validation, committed-client parity, dashboard-type parity, and
two byte-identical regenerations. It exited 0 at uptime
`3.48 3.33 3.35` → `3.04 3.24 3.33` with
`real/user/sys/user+sys = 74.63/74.38/3.86/78.24 s`.

The registered runtime contract checker exited 0 at uptime
`2.99 3.35 3.46` → `3.04 3.32 3.44` with
`real/user/sys/user+sys = 28.10/26.53/1.25/27.78 s`. Package client tests (six),
typecheck and lint exited 0. Repository architecture guardrails exited 0 at uptime
`3.44 3.41 3.46` → `3.13 3.33 3.43` with
`real/user/sys/user+sys = 68.57/59.81/8.58/68.39 s` under the declared 120-second
ceiling. Changed-Python Ruff and `git diff --check` also exited 0.

The package-local architecture checker remains red on two findings that reproduce
unchanged at C03 entry commit `7bf6363d9`: its allow-list rejects the pre-existing
`scripts/generate-runtime-api-client.sh`, and its expected imports omit the existing
canonical-client import in `runtimeApiClient.test.mjs`. The exact entry-snapshot replay
exited 1 with the same two messages. Neither reported path changed in C03; this is an
inherited package-checker finding, not a generated-client product regression or a C03
receipt.

C03 consumes no new mechanism and no widening round beyond the owner already admitted
at C00. The budget stays **42 / 44**, with **3 / 7** rounds spent. Its schema and five
package outputs are closed; the seventh dashboard generated type and exact-byte UI
admission remain the declared C04 boundary.

## C04 strict admission and exact-byte MACHINE closure

The first executable C04 harness attempt used `import.meta.url` under Vitest's browser
transform and could not open the frozen schema; those seven errors are a tooling non-
receipt. After correcting only the fixture locator, the permissive red implementation
produced seven intended failures while the six-class positive control passed: reordered
wire bytes were normalized, nested unknown data was admitted, a generic `changed` class
and class-wide appeal passed, denominator/hash drift passed, a false OpenWorldRisk
freeze passed, and MACHINE downloaded a reserialization. This held the response and UI
markers constant while changing the semantic payload or byte identity.

The dashboard generator atomically refreshed `apps/runtime-dashboard/src/api/types.ts`.
Its immediate second sanctioned regeneration preserved SHA-256
`38b953f3b2fecbc8caed325ba7d79d6873cfadaa06a1aa0cc901855f726cbb00`.
A generated-artifact register parse and an independent `7bf6363d9..working-tree`
family census each returned the same seven outputs with empty symmetric difference:
the OpenAPI snapshot, five package client/type outputs, and dashboard API types.

The new domain owner recursively rejects unknown keys and validates every nested
artifact ref, time scope, certificate, dependency/recompute state, perturbation,
boundary, OpenWorldRisk component, denominator and both absence classes. It recomputes
the server's sorted semantic JSON hash after excluding only `observed_at` and the hash
itself. All six perturbation values remain distinct, `appeal` alone is forced to
instance scope, and a generic `changed` value is impossible. The generated-client
bridge captures `response.clone().arrayBuffer()` before the response reaches generated
JSON parsing, admits only a defensive copy of those bytes, binds run id and requested
replay hash, and uses a never-retain authority query policy. The MACHINE exporter copies
those captured bytes directly into its blob without JSON decode or serialization.

Ten focused tests now pass across the domain, bridge and MACHINE twin. Dashboard
typecheck, targeted ESLint and Prettier pass. The registered runtime contract checker
exited 0 at uptime `4.18 3.33 3.37` → `3.60 3.29 3.35` with
`real/user/sys/user+sys = 34.71/31.31/1.51/32.82 s`. Repository architecture
guardrails exited 0 under the declared 120-second ceiling at uptime
`3.42 3.26 3.34` → `4.61 3.64 3.47`, with
`real/user/sys/user+sys = 95.62/85.07/11.52/96.59 s`; all three observed generated
families were fresh.

C04 changes its three declared mechanisms plus the registered dashboard generated
companion and tests. No widening is required: the budget remains **42 / 44**, with
**3 / 7** rounds spent.

## C05 universal chrome, exports, and truthful absence closure

C05 started with behavioral mutations against the existing shells. Nine assertions
failed for the intended missing properties: changing epoch status/owner `as_of` did
not change the run surface; the two absence kinds had no distinct rendering; the six
perturbation classes and appeal scope were absent; cross-epoch replay had no visible
boundary; the signed packet neither required nor hashed the epoch arm; central chart
evidence omitted epoch semantics; social output dropped the arm; and bureaucratic
admission accepted a malformed temporal record. These were state mutations with stable
component/route markers, not future-name checks.

`TimeSemanticsLabel` now owns one strict `EpochSemantics` grammar and an optional typed
provider. It renders independent valid/transaction/payload/source/observation clocks
without substituting one for owner `as_of`, and visibly distinguishes current, stale,
revalidation-required, contested and not-established states. The run layout admits the
strict epoch projection once, builds one signed packet whose hash includes that arm,
and passes the same packet instance to publication, reviewer-craft and ambient-
telemetry consumers. Runs list and compare render per-run semantics; comparison keeps
two epochs separate and labels the boundary instead of blending them.

The detailed view keeps inspection, replay and captured-byte MACHINE download
available for positive and refusal states. Signer rows render **Authority not
appointed**, their exact typed refusal, institutional dependency wording and
`appointment_is_closure_precondition=false`. The derived recompute gap renders
**Engineering capability not wired**, names
`polisyos.runtime.quality.derived_observations`, and uses an assignable engineering
closure. The behavioral falsifier swaps those rows under the same panel shell and
requires the title, candidate-owner and closure class to switch; it is green. There is
no appoint/bypass control and appointment is not a C05 or CC10 closure precondition.

Certificates switch visibly between stale and current while the surrounding shell is
held fixed; stale output exposes its trigger and revalidation requirement. Derived
dependencies expose inherited staleness and recompute posture. Incident, appeal,
correction, retraction, legal change and discovered bias keep six labels and wire
values; appeal alone is instance-scoped. OpenWorldRisk promotion freeze changes with
the admitted state, and replay lineage exposes a keyboard-focusable epoch boundary.

The strict epoch arm is required before packet signing and flows through the public
packet, React/HTML/Satori/SVG/PNG social outputs, React/plain-text email, bureaucratic
AST, standalone HTML, live DOM and browser print. Missing bureaucratic input becomes
the exact `epoch_projection_not_established` nonreceipt; malformed input fails
admission. The inherited-DOM falsifier exports a source tree with the temporal node,
then removes only that node while preserving the render-root shell: the second raster
input loses the epoch bytes, proving print inherits admitted source DOM rather than
reconstructing a claim. The frozen Russian catalog is byte-identical at working tree
and `HEAD`, SHA-1 `07a1b4fadded69fc3435be9eca235eb85c4c24d4`.

The changed-test blast radius covers 104 tests in 13 files and exited 0 at uptime
`3.29 3.55 3.36` → `4.30 3.76 3.44`, with
`real/user/sys/user+sys = 8.65/29.79/4.67/34.46 s`. The unchanged DS4 primitive tests
add five green cases, and the print/bureaucratic companion pair adds five green cases.
Dashboard typecheck exited 0 at uptime `3.44 3.61 3.39` → `3.46 3.61 3.39`, with
`real/user/sys/user+sys = 14.72/27.83/0.91/28.74 s`. Scoped ESLint covered all 31
changed TypeScript files and exited 0 under its 180-second ceiling at uptime
`3.00 3.52 3.32` → `3.68 3.61 3.36`, with
`real/user/sys/user+sys = 54.21/65.45/3.63/69.08 s`. Delta ESLint, Prettier over all
changed TypeScript/JSON files, and `git diff --check` also exited 0.

The first focused aggregate rerun exposed an incomplete `LocaleProvider` test mock;
after the mock acquired the real optional-i18n surface, all nine affected public-view
cases passed. The first typecheck then rejected a `Blob | MediaSource` test spy before
the spy narrowed on `Blob`; the narrowed harness passed. Both are companion-harness
findings, not product findings. Two earlier full/scoped lint processes were terminated
as tooling nonreceipts because their output sessions and predeclared ceilings were
lost. Two formatter invocations were also nonreceipts: one doubled the package prefix,
and one passed a newline list as a single zsh filename. Neither changed repository
bytes. A first changed-mechanism receipt likewise compared repo-relative status paths
to product-relative plan paths and falsely reported all 20 absent; it is rejected as a
coordinate-frame nonreceipt. The corrected prefix-aware receipt and an independent
literal owner-set census both derive all **20 / 20** C05 mechanisms changed with empty
symmetric difference.

C05 spends no new path and no widening round beyond its admitted preflight owner. The
slice remains **42 / 44** mechanisms with **3 / 7** rounds spent.

## C06 complete denominator — in-scope closure and owner-contract stop

C06 began with the planned behavioral reds. With marker/import strings held fixed, the
new scanner tests first failed because no complete production-file/render-root census
or per-root temporal receipt existed. The landing-slice falsifier then held the DS18
historical freeze and all its receipts constant, added one later decision-bearing root,
and required the current landing check to reject it. A separate route harness supplied
an admitted current epoch while preserving the standalone report/deck print and raster
selectors; both selected roots still contained no epoch node. That proved the route
pages, not `RunDetailLayout`, were the missing owners.

The generic TypeScript compiler scanner now walks every production `.ts`/`.tsx` file
and inventories JSX, `React.createElement`, server/Satori rendering, HTML/SVG templates,
DOM clone/serialization, raster and print roots. Test, story and registered generated
paths are excluded by typed rule. The independently reconciled register carries an
explicit `render_roots_complete|no_render_root` receipt for every admitted source file,
and every root is classified as `decision_bearing`, `non_decision_bearing`, or
`inherits_admitted_dom` with source-bound behavioral evidence where required.

Two denominator derivations agree exactly. `Path.rglob` and `rg --files` each find
1,058 raw dashboard TypeScript/TSX paths with empty symmetric difference; the typed
scanner and registered file set each retain 605 production files with empty symmetric
difference. The scanner and nested register each enumerate 719 render/export roots with
empty symmetric difference. A direct classification/evidence sum and the stored totals
both give **77 obligated / 77 covered**. The scoped recomputing checker emits
`predicate_provenance=independently_reconciled` and those same four counts.

`RunReportPage` and `RunDeckPage` now admit the run-scoped projection independently and
render `TimeSemanticsLabel` inside the exact print/raster roots. Their behavioral test
changes the projection from the typed nonreceipt to admitted current semantics and
requires the selected roots to change. This measured second finding in the standalone
decision-export class consumes the final two reserve paths together: the declaration is
**44 / 44**, with **4 / 7** widening rounds spent. A regex table walk and an independent
column parser each derive 44 unique declared mechanisms and cluster counts
`7 + 6 + 1 + 3 + 20 + 7`; `git diff --name-only` plus the untracked set and an
independent committed-diff plus porcelain-status derivation both prove all 44 have
changed since C00, with empty symmetric differences.

The Atlas primitive-adoption row is measured only while the recomputing DS18 checker is
green. It reports 77/77 today. If a later root invalidates the moving denominator, the
same row becomes `unknown/time_semantics_coverage_not_established` with
`predicate_provenance=not_established`; it does not throw, preserve 100%, or turn the
unknown denominator into zero. The Python post-freeze falsifier and the TypeScript
not-established schema falsifier are green.

The checker also re-anchored 12 C05-moved direct `Badge` identities. An AST scan of the
C04 source and an independent current-source scan matched every old/new site by owner,
syntax and semantic role; all 12 retain their previous debt/benign classification. No
authority role was reclassified, and the complete partition hash now recomputes to
`sha256:88723b991e24cbd4d92d08466714a293ab10a8a8569718be1db7858c089d3163`.

Admitted in-scope receipts:

- five DS18 scanner/register behavioral tests pass, including marker-only evidence
  rejection and the post-freeze landing-slice red;
- 31 standalone report/deck and run-surface tests pass;
- the three focused health-metric current/fail-closed/denial-proxy tests pass;
- dashboard typecheck passes;
- targeted ESLint and Prettier pass for all changed C06 TypeScript/TSX/MJS paths;
- the new Python scanner test passes Ruff and Ruff format; all three changed Python
  files compile;
- the scoped DS18 checker is green at 605 files / 719 roots / 77 obligated / 77 covered.

The local worktree venv lacked `jsonschema>=4.25`, and the offline cache could not
provision it. Those attempts are tooling non-receipts. The lock-identical integration
venv was linked read-only into the worktree and reproduced the scoped checker result.
The whole pre-existing checker/test files have 705 inherited Ruff findings, so a whole-
file Ruff invocation is a baseline-red non-receipt; the new file and Python compilation
checks above are the admitted changed-path evidence.

Two hand-authored, generatorless owner contracts prevent C06 from closing end to end
without violating the slice fence:

1. DS6's `apps/runtime-dashboard/scripts/persist_atlas_evidence.py` duplicates the old
   primitive-adoption row as `not_established`. Its exact admission rejects DS18's
   recomputed 77/77 output with `health-metric rows do not bind the recomputed
   canonical-source projection`. The full health blast radius therefore has 50 green
   tests and three persistence-consumer reds after the independently re-derived denial
   proxy count was corrected from six to seven. The script is other-slice evidence, is
   not generated, and is not a declared DS18 path.
2. DS5's hand-authored
   `architecture/atlas_surfaces/frontend-baseline-debt-manifest.json` content-binds six
   C05-changed resolved-lint sources. The full register checker rejects those six stale
   bindings before its sanctioned supplemental writer may run. The C06 plan explicitly
   forbids editing that DS5 baseline. The same diagnostic also exposes downstream C13
   print and protected-signing receipts that the single C05 packet-producer
   consolidation legitimately moved; refreshing them would rewrite other slices'
   evidence rather than DS18's declared reconciliation.

Both are the explicit stop class: a hand-authored contract owned by another team, with
no generator, blocks the property. Neither is a generated-artifact, contended-file, or
coordination stop. C07 cannot freeze or claim end-to-end green while either admission
consumer rejects the new truth.

## Receipt correction — architecture guardrail predicate was not established

The C02-C04 journal and commit messages asserted that repository architecture
guardrails were green. That claim is withdrawn. The admitted invocation was
`PATH="$PWD/.venv/bin:$PATH" uv run polisyos-tools architecture guardrails check`;
the C02 journal retained only its aggregate exit code and timing, and C03-C04 repeated
the aggregate claim. Those receipts did not retain or reconcile the deep-import
subcheck output, and no direct
`tools/devx/architecture/guardrails.py check` delta was run and read at the delivered
slice head. The hand-back then promoted cluster-local wrapper exits into a slice-head
claim about a predicate they did not evidence.

The mechanism is **command-to-predicate binding failure plus stale cluster receipt**:
an aggregate wrapper exit was treated as proof of a named subpredicate, without a
receipt binding that exit to the direct guardrail engine's complete findings at the
claimed coordinate. A direct check at delivered head `54f9ff4f2` reports 19 new
deep-import creep edges while the same check on `main` reports zero. Therefore the
prior green statements are false receipts, not inherited reds or tooling
nonreceipts. C01-C04's behavioral tests remain evidence for their named product
properties; none of their prior architecture-guardrail statements is admissible.

No implementation remedy begins until this correction is committed. Closure now
requires edge-by-edge classification, a facade or registered expiring exception for
each edge, and a fresh direct branch-versus-`main` guardrail delta proving that the
branch contributes zero creep.

## C06 continuation — 19-edge classification and red receipts

The receipt correction is committed independently at `074a57d43`, before any source
or architecture remedy. The direct delivered-head command then reproduced all 19
creep edges at uptime `2.95 3.54 3.63` → `3.14 3.52 3.62`, with
`user + sys = 26.36 + 7.76 = 34.12 CPU-s` under the declared 120 CPU-second ceiling.
The additional `trust-claim-posture-register` message was the expected local
`env: python: No such file or directory` PATH artifact and is excluded from the delta.

Two independent derivations agree: the guardrail engine's structured violations and
an independent complete AST/public-entrypoint/baseline comparison both return
**19 = 15 Core + 4 Scientist**, with the same edge set.

| Edge | Classification | Remedy and reason |
| --- | --- | --- |
| `runtime.http.openapi_contract -> core.artifacts.manifest` | stable Core artifact ABI | consume `artifacts.ArtifactRef` through the already-supported `polisyos.core` root module namespace |
| `runtime.http.openapi_contract -> core.contracts.control` | stable Core request/response contract | import `EpochValidityBatchResponse` through the already-supported `polisyos.core.contracts` facade |
| `runtime.http.openapi_contract -> core.contracts.decision_validity` | stable Core Decision Validity contract | import all three DTOs through `polisyos.core.contracts` |
| `runtime.http.services.control.run_lifecycle -> scientist.governance.continuous.monitors` | cross-layer persisted monitor read contract | use the existing lazy `polisyos.scientist.governance.continuous` facade; only the exact resolver is exported |
| `runtime.http.services.temporal -> core.artifacts.manifest` | stable Core artifact ABI | consume `artifacts.ArtifactRef` through the already-supported `polisyos.core` root module namespace |
| `runtime.http.services.temporal -> core.artifacts.protocol` | stable Core artifact-store protocol | consume `artifacts.ArtifactStore` through the supported Core root |
| `runtime.http.services.temporal -> scientist.governance.continuous.monitors` | cross-layer persisted monitor artifact/read contract | export the kind, persisted DTO, and resolver through the existing continuous-governance facade |
| `runtime.quality.epoch_staleness_projection -> core.artifacts.manifest` | stable Core artifact ABI | consume type-only `artifacts.ArtifactRef` through the supported Core root |
| `runtime.quality.epoch_staleness_projection -> core.contracts.chronology` | stable Core chronology contract | import the two failures through `polisyos.core.contracts`, where both are already exported |
| `runtime.quality.epoch_staleness_projection -> core.contracts.decision_validity` | stable Core Decision Validity contract | import the three DTOs through `polisyos.core.contracts`, where they are already exported |
| `runtime.quality.epoch_staleness_projection -> core.contracts.runtime` | stable epoch/time projection contract | complete the existing `polisyos.core.contracts` lazy facade and import the epoch/time DTO family there |
| `runtime.quality.epoch_staleness_projection -> scientist.governance.continuous.monitors` | cross-layer six-class monitor artifact contract | export the six strict perturbation arms and persisted event through the existing continuous-governance facade |
| `runtime.quality.epoch_validity_cascade -> core.contracts.runtime` | stable epoch perturbation contract | consume `EpochPerturbationClass` through the existing `core_contracts` facade already imported by the module |
| `runtime.quality.epoch_validity_cascade -> scientist.governance.continuous.monitors` | cross-layer persisted monitor artifact contract | import the exact persisted event through the continuous-governance facade |
| `scientist.governance.continuous.invalidation -> core.artifacts.protocol` | stable Core artifact-store protocol | consume `artifacts.ArtifactStore` through the supported Core root while preserving baseline-covered manifest imports |
| `scientist.governance.continuous.invalidation -> core.artifacts.store` | stable Core artifact write option | consume `artifacts.PutOptions` through the supported Core root while preserving baseline-covered imports |
| `scientist.governance.continuous.invalidation -> core.canon` | stable Core package module | use supported `from polisyos.core import canon`; no new Canon facade is invented |
| `scientist.governance.continuous.monitors -> core.artifacts.protocol` | stable Core artifact-store protocol | consume `artifacts.ArtifactStore` through the supported Core root; baseline-covered sibling imports remain unchanged |
| `scientist.governance.continuous.monitors -> core.contracts.runtime` | stable epoch perturbation contract | import `EpochPerturbationClass` through `polisyos.core.contracts` |

The split is **19 facades / 0 exceptions**. Core's supported root already exposes the
artifact module and every needed artifact/store symbol. The Core contract facade lacks the new epoch/time family;
the Scientist continuous facade lacks the exact persisted-event/read/six-class family.
Two executable import probes failed on those missing exports at uptime
`4.54 3.74 3.62` → `4.50 3.74 3.62`, each with
`user + sys = 0.04 CPU-s`. These are the facade-completion reds; the direct 19-edge
guardrail run is the public-entrypoint red.

The repair adds three mechanism paths: the Core contracts facade, the Scientist
continuous-governance facade, and the shared public-surface contract. It spends two
NEW architectural widening rounds—Core stable-facade completion and Scientist
continuous-governance facade completion—moving **44 → 47 / 44** and **4 → 6 of 7**
rounds. Generated public inventory/reference outputs are companions. The deep-import
baseline and both exception registries remain untouched.

## C06 architecture-guardrail repair closure

The first implementation registered `polisyos.core.artifacts` as an additional public
entrypoint. The facade imports became legal, but the direct guardrail correctly stayed
red because that registration removed historical `core.artifacts` members from the
frozen deep-import baseline. That is a behavioral falsifier of the proposed remedy, not
a license to rewrite the baseline. The repair instead consumes the same stable artifact
ABI through the already-supported `from polisyos.core import artifacts` namespace. The
Core contracts facade exports the epoch/time DTO family; the existing Scientist
continuous-governance lazy facade exports the persisted event resolver and six strict
perturbation arms; only that Scientist facade is added as a supported entrypoint.

The sanctioned public-surface sync ran twice with
`--skip-deep-import-baseline`: the exploratory receipt used
`user + sys = 13.12 + 0.31 = 13.43 CPU-s`, and the corrected receipt used
`13.05 + 0.25 = 13.30 CPU-s`. The deep-import baseline blob remained
`04b18bf5accbaa45a5ebdd60379439f9634095ea` before and after both runs. The
public-surface inventory and reference are the only generated companions.

At the corrected tree, direct branch guardrails report no deep-import failure and only
the expected local `trust-claim-posture-register` PATH artifact, at uptime
`3.33 3.31 3.39` → `3.81 3.45 3.43` with
`user + sys = 44.34 + 13.25 = 57.59 CPU-s`. The same command on `main`
reports the identical sole PATH artifact, at uptime `3.54 3.40 3.42` →
`3.78 3.47 3.44` with `43.46 + 12.52 = 55.98 CPU-s`. Thus the direct
branch/main creep delta is **0 / 0**. Independently, a complete AST walk over
`src/polisyos/**/*.py`, with supported entrypoints parsed from the contract, derives
`3,537` current deep edges and the frozen JSON derives `3,537`; their set difference is
`0 new / 0 missing`.

After Ruff formatted the three touched importer modules, the direct branch check was
replayed on the exact pre-commit working tree. It again emitted no deep-import finding
and only the identical PATH artifact, at uptime `2.77 3.19 3.32` →
`3.26 3.25 3.34` with `user + sys = 41.61 + 11.91 = 53.52 CPU-s`.

Both previously red facade import probes now execute the real imports. The focused
public-facade, epoch projection/cascade, HTTP temporal/validity, Scientist validation,
continuous-governance, and chronology conformance blast radius exits 0 at uptime
`3.27 3.41 3.41` → `3.29 3.39 3.41`, with
`user + sys = 66.59 + 8.55 = 75.14 CPU-s`. The preceding invocation named a removed
integration-test path and exited 4 before an admissible suite receipt; it is a tooling
nonreceipt, not a product finding. Ruff, Ruff format, generated freshness, and
`git diff --check` are green. The remedy remains **19 facade closures / 0 exceptions**,
**47 / 44** mechanism paths, and **6 / 7** widening rounds.

## C07 source freeze

The architecture owner explicitly ruled that the DS5 baseline-manifest stop and DS6
health-persistence stop remain truthful named non-closures but do **not** block C07.
This supersedes the earlier journal sentence that C07 could not freeze while those
owner contracts stayed red; neither owner file is edited or claimed here.

The attached, clean source head
`c553f4c30c2c3b01f01a09eb71f792440c8c2dee` is
`ds18_frontend_freeze_commit`. The scoped recomputing checker ran at that exact source
coordinate and returned `predicate_provenance=independently_reconciled`, 605 production
files, 719 roots, and 77 obligated / 77 covered. It exited 0 at uptime
`2.96 3.18 3.30` → `2.96 3.18 3.30`, with
`user + sys = 3.20 + 0.18 = 3.38 CPU-s`.

An independent direct scanner parse derives 605 files and 719 roots both from its
declared totals and from `len(files)` / the nested root sum. A separate nested-register
walk derives 605 files, 719 roots, 77 decision-bearing-or-inherited obligations and 77
content-bound behavioral receipts, then hashes every registered production file at the
freeze: **0 receipt hash mismatches**. The post-freeze landing rule remains the
invariant: later slices own fresh receipts and behavioral proof for every root they add
or change; this historical freeze remains valid.

## C07 superseding freeze and closeout execution

The first freeze above is historical, not the closeout coordinate. C07 review found
that the positive demonstration fixture had no visible fixture-only authority marker,
and changed-path ESLint then exposed the same hard-coded-copy class across the complete
`EpochStalenessView` component. The component now renders a visible
**Fixture-only evidence** warning, routes all of its chrome through the active locale
owner, and replaces the local boundary arrow with the shared `Glyph` vocabulary. This
is the same C05 surface mechanism one level deeper, not a new mechanism path or widening
round. The English and Ukrainian catalogs are the active product locales; the Russian
catalog remains frozen and byte-untouched.

The first no-writer coverage check after that source change correctly failed on the
stale file/root receipts while every marker remained present. The sanctioned DS18
writer refreshed only the DS18 coverage object and restored 605 files / 719 roots /
77 obligated / 77 covered. This is a live witness for the landing-slice rule: changing
an owned render root invalidates its own receipt instead of preserving the historical
total.

Active-locale parity initially returned five reds. Three were the new nonnumeric ICU
variables (`disposition`, `relation`, `requirements`); the active catalog composition
receipts had also moved; and the untouched legacy Russian receipt had already been
stale since `957841569` added seven Russian leaves. No Russian catalog byte was changed.
An independent Node walk and Python JSON walk both derive 2,733 leaves in each active
catalog and 2,456 legacy Russian leaves. The two languages independently derive the
legacy key and leaf hashes now frozen in the test. The parity runner and a separate ICU
AST walk agree on 366 active non-count uses and the exact use-set digest. After those
composition receipts were repaired, the complete parity file passes. The parity test
is a mandatory P39 companion; the mechanism declaration remains unchanged.

The attached source/evidence commit
`3011c9584a0327661c8f5a9b695a1769ddb64385` supersedes
`c553f4c30c2c3b01f01a09eb71f792440c8c2dee` as
`ds18_frontend_freeze_commit`. At that exact clean commit, the scoped checker exits 0
at uptime `1.38 1.93 2.28` → `1.43 1.94 2.28`, with
`user + sys = 3.25 + 0.12 = 3.37 CPU-s`, and reports
`predicate_provenance=independently_reconciled`, 605 files, 719 roots and 77/77.

An independent direct scanner/register walk at the same commit exits 0 at the same
uptime pair with `user + sys = 2.25 + 0.11 = 2.36 CPU-s`. Scanner-declared and nested
counts are 605/719; register-declared and nested counts are 605/719; the file-set
symmetric difference is empty; the partition is 33 decision-bearing + 44
`inherits_admitted_dom` = 77 obligated; all 77 carry behavioral evidence; and all 605
source digests are fresh. This is the final freeze denominator.

### Six measured C07 waves

| Wave | Predeclared CPU ceiling | Admitted `user + sys` | Result |
| --- | ---: | ---: | --- |
| backend | 112.71 s, from the prior 75.14 s focused blast radius × 1.5 | 93.96 + 9.27 = **103.23 s** | exit 0 for the named epoch projection/cascade, Decision Validity, monitor/invalidation/lifecycle, temporal HTTP and chronology-conformance set; uptime `1.37 1.84 2.22` → `2.25 1.96 2.22` |
| contract/generated family | 226.45 s, from 27.78 + 78.24 + 75.14, then × 1.25 | **107.64 s** across seven directly timed commands | runtime contract, public-facade/docs blast radius, both sanctioned generators, package client tests/typecheck and exact registered-output byte check all exit 0; no generated byte moves |
| frontend | 165.35 s, from 34.46 + 28.74 + 69.08, then × 1.25 | 120.11 + 6.30 = **126.41 s** | named semantic/component/export/route/i18n tests, dashboard typecheck and ESLint over every slice-changed JS/TS path exit 0; uptime `2.57 2.27 2.23` → `3.38 2.67 2.40` |
| checker | 212.94 s, two 83.97 s direct checks plus 45.00 s semantic allowance | **153.50 s** | branch/main direct guardrail delta 0/0, scoped coverage green, landing-slice falsifier green, and the health file remains exactly the owner-declared three-red set |
| visual | 90.00 s, from the earlier 57.04 s six-case run plus contention margin | 50.31 + 6.70 = **57.01 s** | six DS18-only snapshots pass without a writer; uptime `6.58 4.17 3.08` → `5.59 4.19 3.16` |
| accessibility | initial 58.13 s rejected after the package command revealed an 85-file denominator; replay ceiling is 485.87 s for that package command plus 6.44 s for the DS18 witness | 269.99 + 53.92 + 3.84 + 0.42 = **328.17 s** | package component accessibility and the separate DS18 absence/positive axe witness exit 0 |

The first aggregate contract timing used a zsh subshell, and its `0.04 + 0.06` report
measured only that intermediate shell. A `/usr/bin/time` wrapper around another zsh
subshell repeated the same defect. Both are timing non-receipts. The admitted contract
total instead sums direct timings: runtime contract 46.04, public-surface tests 41.30,
package generation 6.83, dashboard generation 8.62, client tests 1.00, package
typecheck 3.69 and byte check 0.16 CPU-seconds.

The first frontend aggregate passed logic and typecheck but supplied
`policy-engine/apps/...` from inside the already-resolved `policy-engine/` prefix. Its
empty Git path set left ESLint without operands and was interrupted after the
coordinate defect was identified. It is a tooling non-receipt. The admitted replay
uses `apps/runtime-dashboard` as the pathspec and strips the Git-output prefix exactly
once before linting the complete slice delta.

The direct branch guardrail at the freeze emits no deep-import finding and only the
expected local `trust-claim-posture-register` `env: python` PATH artifact, at uptime
`2.11 2.64 2.46` → `2.08 2.56 2.43` with
`user + sys = 40.43 + 11.13 = 51.56 CPU-s`. The attached `main` worktree at
`dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f` emits the identical sole PATH artifact and
no deep-import finding, at uptime `1.99 2.53 2.42` → `1.98 2.43 2.39` with
`40.30 + 11.03 = 51.33 CPU-s`. Direct creep is therefore **branch 0 / main 0**. The
independent complete AST/public-entrypoint/baseline derivation remains 3,537 observed /
3,537 frozen, 0 new / 0 missing; no Python importer changed after that derivation.

The four DS18 coverage tests pass at `user + sys = 11.30 + 0.64 = 11.94 CPU-s`,
including the post-freeze falsifier: a later decision-bearing root with the historical
DS18 receipt held fixed must raise `landing_slice_reconciliation_required` for the
landing slice while the DS18 historical freeze stays valid. The health test returns
the exact independently expected three DS6-owner reds and no fourth red, with
`user + sys = 32.60 + 2.70 = 35.30 CPU-s`: persistence through Core CAS, hostile caller
PATH, and hostile caller `NODE_OPTIONS` all stop at the same stale persistence owner.

### Snapshot and semantic readback

Playwright enumerates six passing visual cases and the DS18 snapshot root independently
contains six PNGs with the same identities:

- real declared institutional and engineering absence;
- content-bound positive fixture, visibly marked fixture-only;
- stale certificate plus dependent derivation/recompute posture;
- all six perturbation classes with appeal still instance-scoped;
- OpenWorldRisk promotion freeze;
- keyboard-focused cross-epoch replay boundary with both immutable epoch refs.

All six images were inspected after generation; the stale-cascade and replay images
regenerated after localization and were re-inspected at original resolution. The
absence-class behavioral falsifier is green: changing only the underlying absence arm
switches between **Authority not appointed** with an institutional dependency and
**Engineering capability not wired** with
`polisyos.runtime.quality.derived_observations` plus an assignable engineering closure.
Neither arm can inherit the other's closure language. Replay and the exact-byte MACHINE
twin remain enabled in both, no appoint/bypass action exists, and appointment is not a
closure precondition.

### Closeout capability claim and carried rows

DS18 closes the epoch family's audit/API/dashboard/MACHINE `surface_missing` state at
the frozen denominator, the generated bridge/consumer/semantic-test gaps for both epoch
operations, the six-class live projection, stale/dependency/OWR/replay chrome, DS4
consumption, and the truthful declared-absence surface. It does not promote the six
upstream states below beyond the evidence actually present. These are the exact row
texts for the register owner; there is deliberately no source-synchronization row:

| Row | State | Owner / closure text |
| --- | --- | --- |
| Epoch predicate-policy signer | `absent/unallocated` | Institutional appointment may occur only after real-user deployment; DS18 closes truthful refusal rendering, and appointment is not a DS18 closure precondition. |
| Epoch transition signer | `absent/unallocated` | Institutional appointment may occur only after real-user deployment; DS18 closes truthful refusal rendering, and appointment is not a DS18 closure precondition. |
| Independent epoch-history holder / whole-history authenticity | `absent/unallocated` | No independent institutional holder is appointed; preserve the scoped limitation and never claim whole-history authenticity until that institution supplies it. |
| Positive epoch-transition production | `implemented_but_not_orchestrated` | Candidate owner `polisyos.runtime.quality.epoch_validity_cascade.EpochValidityTransitionProducer.produce_and_persist`; only a real production call can close orchestration. |
| Positive epoch-transition verification | `producer_missing` | Candidate owners `polisyos.core.contracts.EpochTransitionVerifier` and `polisyos.scientist.validation.DecisionValidityService`; configure a provenance-bearing verifier rather than treating `NoEpochTransitionVerifier` as positive evidence. |
| Epoch-inheritance/recompute-status projection and read bridge | `producer_missing + bridge_missing` | Candidate owner `polisyos.runtime.quality.derived_observations`; emit the owner-bound epoch/recompute status and wire its temporal read bridge. This waits on engineering assignment, not institutional appointment. |

Two owner-contract non-closures remain alongside those carried rows and do not block
the C07 product closeout:

| Owner stop | State / exact owner action |
| --- | --- |
| DS5 frontend-baseline owner — `architecture/atlas_surfaces/frontend-baseline-debt-manifest.json` | Its content bindings predate the DS18 C05 sources. DS5 must refresh its hand-authored baseline and dependent receipts; DS18 does not edit or claim that evidence. |
| DS6 Atlas-health persistence/provenance owner — `apps/runtime-dashboard/scripts/persist_atlas_evidence.py` and its DS6-owned health provenance tuple | The persister still emits `primitive_adoption` as `unknown/not_established` with the now-false no-exhaustive-relation basis. DS6 must re-anchor that producer/provenance family to the recomputed DS18 relation; DS18 does not rewrite it. |

The closeout pattern pass re-read P03/P04/P05/P07/P08/P10/P14/P15,
P27/P29/P31/P32/P33 and P35-P41. The resulting pattern is one strict owner projection,
one exact-byte admission boundary, one DS4 time grammar, one complete independently
reconciled render denominator, and semantic falsifiers that mutate the underlying
state while holding markers fixed. The final mechanism budget is **47 / 44**, with
**6 / 7** widening rounds spent, **19 facade remedies / 0 exceptions**, and no hidden
path or baseline update.

The first final blob readback derived the continuation path set correctly twice but
passed its repo-root members to `git ls-tree` from inside `policy-engine/`, so every
lookup was prefixed twice and the command was rejected as a coordinate-frame
non-receipt. This is the same class as the rejected frontend lint invocation above.
The property-level readback resolves `git rev-parse --show-toplevel` once and executes
both set derivations and every tree lookup from that single top-level coordinate; no
per-path substitution is admitted.

## Reopened receipt correction — selected C07 waves were not a complete predicate set

The C07 closeout ran six measured waves and reported every wave green. That statement
described the commands selected for those waves; it did not establish that the
selection covered every binding predicate. The wave set was assembled manually from
the six category names in C07 step 2, the slice's changed-mechanism blast radius, and
the timings already available for those commands. It was not derived from an
exhaustive predicate inventory or reconciled against every focused command in plan
section 15. In particular, the checker wave was composed from the direct architecture
guardrail delta, the scoped DS18 time-semantics coverage check and landing falsifier,
and the Atlas health-metrics test. It did **not** run
`architecture/atlas_surfaces/check_frontend_disposition_register.py --check`, despite
that command being named separately in section 15, or the three Atlas test files that
enforce its writer, baseline-transition, and reference-identity properties.

The result is the same disease as the earlier C02-C04 receipt failure, one level up:
**selected-wave-set-as-complete command-to-predicate binding failure**. A green result
for every selected command was promoted into a green closeout claim for the slice,
without a reconciliation proving that the selected command set equalled the required
predicate set. The omitted register predicate carried 37 DS18-attributable CLI
findings and 17 DS18-attributable enforced-test failures at merge. Four test failures
were the already-declared DS5 baseline-manifest non-closure; thirteen were neither run
nor disclosed. The earlier six-wave green claim is therefore withdrawn as a complete
C07 receipt; its individual command results remain evidence only for the predicates
those commands actually exercised.

There was another known predicate outside the selected set: runtime route/Rego
authorization parity. It was not named in section 15 or the recorded C07 wave command
set. The architecture owner's post-merge repair at `49e969e16` added the missing
`runtime.run.epoch_staleness -> ownership_verified` mirror under `runs.review`; that
repair stands and DS18 neither reverts nor duplicates it. Within this reopened round,
the required branch-versus-`main` matrix explicitly includes both the full frontend
register family and the 24-case Rego parity test. No renewed completeness claim will
be made from category names alone: each closeout predicate must be bound to its exact
command and read result.

The architecture-owner ruling for the DS5 artifact is deliberately narrow. DS18 may
re-anchor exactly six `lint_resolution_content_hash` bindings whose bytes DS18 itself
changed: the C06 bindings for `PublicationPacketPanel.tsx`,
`publicationPacket.test.ts`, `publicationPacket.ts`, and `RunDetailLayout.tsx`, plus
the C07 bindings for `quantityChartSemantics.test.tsx` and
`quantityChartSemantics.tsx`. Every other manifest binding and every non-binding field
remain closed: no lifecycle or disposition value, no `authority` block, no C13 print
or protected-signing evidence, and no DS5 plan, journal, or receipt may move. A need
for a seventh binding or any non-binding manifest change is a stop, not an implicit
widening. Only after those six own-blast-radius hashes are current may the sanctioned
descriptor writers refresh their derived register rows.

### Reopened repair — owned bindings, sanctioned projections and real defects

The six-binding ruling was applied literally. `shasum -a 256` and an independent
Python `hashlib` walk agreed on the replacement hashes: C06
`PublicationPacketPanel.tsx` `80000ffa…`, `publicationPacket.test.ts` `86d7e6b4…`,
`publicationPacket.ts` `16c3687f…`, and `RunDetailLayout.tsx` `f4533fee…`; C07
`quantityChartSemantics.test.tsx` `b93d0d93…` and
`quantityChartSemantics.tsx` `746ee78a…`. A semantic before/after comparison found
exactly those six changed binding rows, identical binding-key sets, and equality for
every non-binding manifest value. `validate_baseline_manifest(...,
verify_source_bytes=True)` then returned no error. No seventh binding and no other
manifest field moved.

`--write-supplemental` refreshed five descriptor-derived authority rows and no peer
row; it returned nonzero only because downstream reference families were still stale.
The first DS10 family attempt then failed before promotion on three ambiguous
`call_expression` creation anchors. The root cause was a proxy mismatch: the textual
reference census selected wrapper **function declaration** lines, while
`_c21b_identity_anchor` treated every line containing the function name as a call.
The generic anchor now classifies exported and local wrapper declarations before the
call-expression arm. Its complete protected-signing census test moved red to green.
The resulting denominator is **31** by two derivations: the AST writer emitted 31
identities and an exit-checked `rg` unique-line census over both declared roots found
31. The stale 29 test constant moved to 31.

The DS10 family also correctly refused to hide the inherited C13 print-evidence red.
Its exact external admission still described only two historical mismatches, while a
complete receipt-binding walk found six DS18-moved sources. Python receipt comparison
and independent `shasum` agreed on all six: `AmbientTelemetryHud.tsx`,
`OperatorCraftPanel.tsx`, `RunDetailLayout.tsx`, `RunReportPage.tsx`,
`RunReportPage.test.tsx`, and `runtime-dashboard.visual.spec.ts`. The admission was
rebound to those exact expected/current hash pairs; it still replays the verified
bytes and rejects any seventh mismatch. This does not refresh or close the DS6 receipt:
the full checker continues to emit its one C13 finding. With that honest residual
bound, `--write-ds10-capability-discovery` promoted the protected census and report
atomically; its baseline candidate was byte-identical before and after. Timing was
`user + sys = 115.20 + 12.74 = 127.94 CPU-s`, uptime
`2.82 2.99 3.37` → `4.27 3.45 3.50`.

The thirteen undisclosed failures resolved as follows:

| Enforced failure | Instrument | Outcome |
| --- | --- | --- |
| `test_authority_debt_corruptions_fail_closed` | `--write-supplemental` | stale descriptor row; refreshed, corruption probe remains fail-closed |
| `test_ds11_trust_presentation_writer_is_exact_idempotent_and_forgery_closed` | current-context historical projection in the checker | real validator defect; later required fields and peer receipts no longer contaminate the C04 candidate, while a forged owned target remains red |
| `test_every_authority_presentation_prop_is_branded_or_typed_debt` | `--write-supplemental` | stale descriptor rows refreshed |
| `test_writer_removes_only_retired_authority_presentation_rows` | `--write-supplemental` | stale descriptor rows refreshed; peer-row preservation remains exact |
| `test_c21b_protected_probe_retains_hybrid_identity_multiplicity` | DS10 protected-signing writer | stale identity census refreshed; duplicate construct still raises both observation and count drift |
| `test_c21b_validator_replays_migrated_protected_probe_identities` | DS10 protected-signing writer | live 31-identity probe replays cleanly |
| `test_c21c_surgical_writer_is_idempotent_with_navigation_residual` | supplemental/identity refresh plus its no-write surgical replay | stale peer identities removed; the C21c transform is byte-idempotent and keeps the declared navigation residual |
| `test_surgical_writer_preserves_the_217_row_historical_value` | current-context historical projection in the checker/test | real test predicate defect; the DS8-B owned field validates under the live schema, malformed owned data remains red, and all 217 historical rows remain byte-preserved |
| `test_c11b_cache_posture_debt_closes_after_typed_consumer` | `--write-supplemental` | stale peer-row cascade; typed-consumer proof itself remained valid |
| `test_c14a_local_state_envelope_owner_debt_binds_absent_producer_contract` | `--write-supplemental` | stale peer-row cascade; producer-contract falsifier remained valid |
| `test_c21d_multi_site_authority_sink_ignores_navigation_only_changes` | `--write-supplemental` | authority sink identities refreshed; semantic site/hash removal remains red while navigation-only movement stays green |
| `test_ds10_baseline_candidate_reanchors_only_owned_source_bytes` | the six ruled manifest bindings | stale DS18-owned content bindings; candidate is now byte-idempotent and source-valid |
| `test_ds10_protected_signing_census_adds_the_complete_stable_identity_set` | wrapper-classification repair plus DS10 writer | real writer defect and stale 29 denominator repaired to the independently derived 31 |

The first focused replay after the writers returned 11 green and the two historical
future-schema failures above; `user + sys = 164.78 + 16.65 = 181.43 CPU-s`, uptime
`3.92 3.41 3.49` → `2.59 3.21 3.40`. After the property-level projection repair,
those final two pass with both negative controls at
`73.94 + 7.91 = 81.85 CPU-s`, uptime `2.52 3.10 3.34` →
`2.68 3.06 3.30`. This is one same-class-one-level-deeper repair, not two exception
instances.

The register now carries the real DS18 freeze
`3011c9584a0327661c8f5a9b695a1769ddb64385`, verified as a commit and an ancestor of
the branch. The landing falsifier no longer injects `"f" * 40`: it asserts that live
coordinate, holds its stored receipts fixed, adds one later decision-bearing root to
the recomputed scan, and observes `landing_slice_reconciliation_required`. The
historical freeze remains valid. The focused test passes at
`user + sys = 2.45 + 0.19 = 2.64 CPU-s`.

The first full delta receipt is now **branch 1 / main 38** findings. Branch emits only
the shared C13 print-evidence residual at
`user + sys = 98.58 + 9.46 = 108.04 CPU-s`, uptime
`2.11 2.66 3.10` → `3.18 2.87 3.14`. `main` emits that same row plus 37 DS18-moved
rows: six authority, six ruled baseline bindings, fifteen missing/renamed TypeScript
bindings, eight ambiguous TypeScript bindings, one TypeScript content drift and one
expected-count drift. Its timing is `97.44 + 9.28 = 106.72 CPU-s`, uptime
`3.09 2.85 3.13` → `3.13 2.89 3.11`. Thus DS18's register-checker delta is zero;
the inherited one remains visible on both sides.

### Final reopened verification — exact delta shape

The first paired Atlas replay after arming the freeze exposed a branch-only failure:
one historical test still expected the pre-freeze bare denominator-drift label. That
was DS18's test predicate, not inherited debt. Its assertion now requires the armed
`landing_slice_reconciliation_required` label. The same replay also showed that an
existing DS10 external-admission test had accidentally been made green on the branch
even though it is part of the inherited red set the owner directed this round to
preserve. Its historical expected set was restored; the test is red on both refs and
continues to expose the admitted C13 residual. This was a delta-shape correction, not
an attempt to make an absolute suite green.

The final three-file Atlas replay is therefore **37 failures on the branch / 54 on
`main`**, with **37 shared, 0 branch-only and exactly 17 main-only**. The branch run
used `user + sys = 1339.36 + 82.23 = 1421.59 CPU-s`, uptime
`2.96 3.32 3.66` → `3.73 3.35 3.41`, within the declared 2226.19 CPU-s ceiling.
The `main` run used `1632.60 + 99.61 = 1732.21 CPU-s`, uptime
`2.47 2.81 3.05` → `2.24 3.71 3.89`; the second uptime sample was recovered after
the completed output, so it is an environment/load receipt rather than an exact
process-boundary sample. Independent reads of each ref's pytest `lastfailed` cache,
restricted to the three invoked Atlas files, reproduced 37 and 54. Set subtraction
reproduced 0 branch-only and 17 main-only; comparison with the architect-supplied
17-node set returned no missing and no unexpected member.

The exact 37-node shared set is below; every identifier is relative to the common
`architecture/atlas_surfaces/` prefix:

```text
test_atlas_enforcement.py::AtlasEnforcementTests::test_authority_escape_exemptions_are_exact_owned_and_current
test_atlas_enforcement.py::AtlasEnforcementTests::test_authority_issuer_requires_generated_exhaustiveness_and_runtime_novelty
test_atlas_enforcement.py::AtlasEnforcementTests::test_c13a_terminal_dispositions_have_live_census_and_composer_rebind
test_atlas_enforcement.py::AtlasEnforcementTests::test_full_corruption_probes_exercise_removed_query_producer
test_atlas_enforcement.py::AtlasEnforcementTests::test_generated_owner_receipt_and_status_bridge_are_content_bound
test_atlas_enforcement.py::AtlasEnforcementTests::test_lint_enforcement_executes_the_three_architecture_engines
test_atlas_enforcement.py::AtlasEnforcementTests::test_offline_queue_denominator_tracks_scanned_production_sources
test_atlas_enforcement.py::AtlasEnforcementTests::test_offline_queue_type_rejects_authority_action_kind
test_atlas_enforcement.py::AtlasEnforcementTests::test_persistence_construction_census_is_source_complete_and_bounded
test_atlas_enforcement.py::AtlasEnforcementTests::test_query_construction_and_producer_censuses_are_source_complete
test_atlas_enforcement.py::AtlasEnforcementTests::test_query_construction_options_resolution_is_required_and_nonsemantic
test_atlas_enforcement.py::AtlasEnforcementTests::test_real_illegal_edges_fail_custom_and_dependency_engines
test_atlas_enforcement.py::AtlasEnforcementTests::test_unknown_authz_decision_never_defaults_authority_surface_to_allow
test_frontend_disposition_register.py::DS5LineAddressCensusTests::test_c21b_real_gate_ignores_moved_construct_and_rejects_rename
test_frontend_disposition_register.py::DS5LineAddressCensusTests::test_c21c_real_gate_ignores_json_move_but_rejects_rename_and_content
test_frontend_disposition_register.py::DS5LineAddressCensusTests::test_ds5_line_address_complete_partition_is_derived_from_live_register
test_frontend_disposition_register.py::DS6C13PrintTransitionTests::test_independent_receipt_binds_the_full_conjunction_and_current_bytes
test_frontend_disposition_register.py::DS6RegisterTransitionTests::test_c06_transition_is_surgical_idempotent_and_rejects_bypass
test_frontend_disposition_register.py::DS8BPostFreezeTransitionTests::test_status_companion_maps_only_the_two_regeneration_drifts
test_frontend_disposition_register.py::DS8StrangleCoverageTests::test_companion_baseline_candidate_reanchors_only_three_source_bytes
test_frontend_disposition_register.py::DS8StrangleCoverageTests::test_companion_reference_reanchors_resolve_without_peer_drift
test_frontend_disposition_register.py::DS8StrangleCoverageTests::test_status_candidate_reanchors_only_reconciled_receipts
test_frontend_disposition_register.py::DS9C07AdjudicationTests::test_all_18_opening_objects_have_one_checked_disposition
test_frontend_disposition_register.py::PersistenceConstructionCensusTests::test_storage_construction_rows_validate_explicit_adjudication
test_frontend_disposition_register.py::ProducerBindingDebtTests::test_auth_session_revision_debt_binds_generated_auth_me_contract
test_frontend_disposition_register.py::ProducerBindingDebtTests::test_c06_waist_owner_debts_bind_remaining_independent_planes
test_frontend_disposition_register.py::ProducerBindingDebtTests::test_c07b_dashboard_generated_client_debt_binds_single_owner_strangle
test_frontend_disposition_register.py::ProducerBindingDebtTests::test_capability_state_vocabulary_matches_the_failure_register
test_frontend_disposition_register.py::ProducerBindingDebtTests::test_report_projects_capability_states_and_closure_signal
test_frontend_disposition_register.py::ProducerBindingDebtTests::test_schema_requires_capability_states_and_closure_signal_only_for_producer_binding_debt
test_frontend_disposition_register.py::ProducerBindingDebtTests::test_supplemental_refresh_preserves_terminal_history_and_changes_only_the_derived_set
test_frontend_disposition_register.py::StructuredReferenceIdentityTests::test_live_c21c_selector_hashes_are_complete_and_frozen
test_frontend_disposition_register.py::TypeScriptReferenceIdentityTests::test_c21d_live_register_identity_census_preserves_every_distinct_binding
test_frontend_disposition_register.py::TypeScriptReferenceIdentityTests::test_c21d_real_composer_move_relocates_unique_badges_and_keeps_reds
test_frontend_disposition_register.py::TypeScriptReferenceIdentityTests::test_c21d_retired_address_owners_are_absent_and_counts_are_complete
test_frontend_disposition_register.py::TypeScriptReferenceIdentityTests::test_def21_additive_role_preserves_ds5_identity_bytes
test_frontend_disposition_register.py::test_ds10_writer_carries_only_the_exact_external_c13_receipt_nonclosure
```

The exact 17-node `main`-only set uses that same common prefix:

```text
test_frontend_baseline_debt_manifest.py::FrontendBaselineDebtLifecycleTests::test_architecture_origin_active_and_resolved_form_an_exact_partition
test_frontend_baseline_debt_manifest.py::FrontendBaselineDebtLifecycleTests::test_lint_origin_active_and_resolved_form_an_exact_partition
test_frontend_baseline_debt_manifest.py::FrontendBaselineDebtLifecycleTests::test_resolution_content_bindings_cover_exact_derived_roles_and_live_bytes
test_frontend_baseline_debt_manifest.py::FrontendBaselineDebtLifecycleTests::test_vitest_accepts_the_exact_open_or_c16_resolved_lifecycle
test_frontend_disposition_register.py::AuthorityPresentationCensusTests::test_authority_debt_corruptions_fail_closed
test_frontend_disposition_register.py::AuthorityPresentationCensusTests::test_ds11_trust_presentation_writer_is_exact_idempotent_and_forgery_closed
test_frontend_disposition_register.py::AuthorityPresentationCensusTests::test_every_authority_presentation_prop_is_branded_or_typed_debt
test_frontend_disposition_register.py::AuthorityPresentationCensusTests::test_writer_removes_only_retired_authority_presentation_rows
test_frontend_disposition_register.py::DS5LineAddressCensusTests::test_c21b_protected_probe_retains_hybrid_identity_multiplicity
test_frontend_disposition_register.py::DS5LineAddressCensusTests::test_c21b_validator_replays_migrated_protected_probe_identities
test_frontend_disposition_register.py::DS5LineAddressCensusTests::test_c21c_surgical_writer_is_idempotent_with_navigation_residual
test_frontend_disposition_register.py::DS8BPostFreezeTransitionTests::test_surgical_writer_preserves_the_217_row_historical_value
test_frontend_disposition_register.py::ProducerBindingDebtTests::test_c11b_cache_posture_debt_closes_after_typed_consumer
test_frontend_disposition_register.py::ProducerBindingDebtTests::test_c14a_local_state_envelope_owner_debt_binds_absent_producer_contract
test_frontend_disposition_register.py::TypeScriptReferenceIdentityTests::test_c21d_multi_site_authority_sink_ignores_navigation_only_changes
test_frontend_disposition_register.py::test_ds10_baseline_candidate_reanchors_only_owned_source_bytes
test_frontend_disposition_register.py::test_ds10_protected_signing_census_adds_the_complete_stable_identity_set
```

The remaining mandatory branch-versus-`main` matrix is:

| Predicate | DS18 branch | `main` | Delta conclusion |
| --- | --- | --- | --- |
| Frontend disposition CLI | 1 shared C13 finding; 108.04 CPU-s; uptime `2.11 2.66 3.10` → `3.18 2.87 3.14` | 38 findings; 106.72 CPU-s; uptime `3.09 2.85 3.13` → `3.13 2.89 3.11` | 37 DS18 findings closed; branch-only 0 |
| Three Atlas test files | 37 failures; 1421.59 CPU-s; uptime `2.96 3.32 3.66` → `3.73 3.35 3.41` | 54 failures; 1732.21 CPU-s; uptime `2.47 2.81 3.05` → `2.24 3.71 3.89` | exact shared 37; exact main-only 17; branch-only 0 |
| Architecture guardrails | deep-import creep 0; only shared local PATH artifact; 33.68 CPU-s | deep-import creep 0; identical PATH artifact; 33.54 CPU-s | creep 0 / 0 |
| Runtime/Rego authorization parity | 24/24 pass; 38.40 CPU-s | 24/24 pass; 38.66 CPU-s | identical green |
| Atlas health metrics | 20 pass / exact shared 3 red; 25.11 CPU-s | 20 pass / same 3 red; 25.08 CPU-s | no fourth red |
| DS18 freeze census | 605 files, 719 roots, 77 obligated / 77 covered, 0 missing and 0 digest mismatch; 2.37 CPU-s | identical 605 / 719 / 77 / 77 / 0 / 0; 2.38 CPU-s | identical green |

Guardrail uptime was `2.12 3.40 3.76` → `2.63 3.34 3.72` on both refs;
Rego parity used `2.74 3.35 3.72` → `3.10 3.39 3.71`; Atlas health used
`2.94 3.34 3.69` → `3.62 3.47 3.73`; and the freeze census used
`3.30 3.41 3.70` → `3.35 3.42 3.70`. The guardrail's identical local
`trust-claim-posture-register` PATH failure, the identical unavailable CP-SAT
collection, and the enforcement scanner's identical Node stack-size failure remain
environmental non-findings and were not repaired or promoted into product debt.

The live-coordinate landing falsifier reports exactly
`ds18_time_semantics_landing_slice_reconciliation_required:missing=['apps/runtime-dashboard/src/features/later/LaterDecision.tsx']:extra=[]`
at `user + sys = 1.95 + 0.07 = 2.02 CPU-s`, uptime
`3.15 3.37 3.68` → `3.13 3.36 3.68`. This proves the landing-slice label is armed;
DS18 has not pre-reconciled any later slice's roots.

The prior DS5 owner stop is superseded only for the six content bindings named in the
architecture ruling: those six are now closed, and every other DS5 field remains
untouched and outside DS18. The DS6 Atlas-health persistence/provenance owner stop
remains unchanged, visible as the same three reds on both refs. No deep-import
baseline, debt register, DS5 plan/journal/evidence, or non-ruled manifest field moved.

This reopening adds no mechanism path and spends no widening round. The budget remains
**47 / 44 mechanism paths with 6 / 7 widening rounds spent**. The over-ceiling state
and prior facade widening remain exactly as previously declared; this receipt repair
uses existing checker/test paths plus mandatory journal, register, report and the
six-row baseline companion authorized by the architecture owner.
