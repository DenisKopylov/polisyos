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
