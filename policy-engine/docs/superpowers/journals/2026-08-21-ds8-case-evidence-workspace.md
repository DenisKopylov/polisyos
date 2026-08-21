# DS8 Case & Evidence Workspace execution stop journal

Date: 2026-08-21

Branch: `codex/atlas-ds8-planning`

Approved specification: `docs/plans/active/atlas-slices/DS8-case-evidence-workspace.md`
at `d7068d41f44f0358f89e39871ddad6a5bf7ca232`

User-directed immutable execution base: `6049bf450c298885fa6b9077a144766b5fcd7c7a`

## Outcome

Execution stopped during C00 preflight on the approved plan's canonical C01
stop condition: `artifact_missing`. Production-source functions can compile a
runtime Policy Design Case graph and persist that graph and a `DesignRecordV0`,
but their persistence callers are test-only: no live production path persists
a `DesignRecordV0` into an authorized core-run closure with run/case/tenant
binding. A positive C01 resolver fixture would therefore invent the mock
authority, builder, global index, or unrelated persistence path that the stop
rule forbids.

No C01-C08 mechanism was started. This journal is the only repository/worktree
write made after binding the execution base during this pass. No production
byte, test, OpenAPI schema, generated client, governed register, dependency
lockfile, snapshot, or plan line 7 changed.

`artifact_missing` is the canonical lookup and execution-stop label. The full
case-inspection chain remains `producer_missing + bridge_missing +
consumer_missing + semantic_test_missing` under P01/P02. P05/P15 prevent
candidate S2 material from being promoted by presence, while P31/P32 require
one real resolve-bind-verify closure rather than a resolver-local exception.

## Base fence

The Git prefix from the product-root working directory is `policy-engine/`.
Two complete Git tree comparisons independently enumerated the delta from the
planning base `3d44989c63de564d026004781ae64d92031134ff` to requested `main`
`6049bf450c298885fa6b9077a144766b5fcd7c7a`. Both returned exactly one path:

```text
M policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
```

The delta is documentation-only. `main` was merged append-only into the
attached branch at `09841908cf04d9d9c4b2147d8d83e01a990ca9bd`; the branch's
merge-base with the requested base reads back as the full requested hash. The
approved plan's older frontmatter base was not rewritten: the later execution
instruction is the authority for this run and this journal records the bind.

`corepack pnpm install --frozen-lockfile` completed exit 0 in 1.6 seconds under
a fixed 180-second ceiling before frontend/generated-client evidence. It made
no tracked change. The worktree-local virtual environment lacked the required
test modules; Python receipts below used the repository environment with
`PYTHONPATH=src`, so imports resolve this worktree's source. No environment was
provisioned after the stop became established.

## Artifact-role preflight

| required source | existing producer/persistence | run-closure edge and identity result | C01 ruling |
| --- | --- | --- | --- |
| core run closure | `RunContext.add_output` appends unroled `ArtifactRef`s to `RunManifest.outputs`; the workflow executor adds final state, report and optionally research DAG | manifest has run/tenant identity but no DesignRecord output role | no allowed DesignRecord root |
| `runtime.policy_design_case` profile | NL pipeline helper constructs `case_id`, `run_id`, `job_id`, `tenant_id` and persists a profile | the production `natural_language_run` route is explicitly `legacy_shadow`; NL pipeline execution is withheld, and the profile is not a core-run output | not an authorized closure source |
| `runtime.policy_design_case_graph` | `compile_runtime_policy_design_case` creates a strict graph carrying run/job/tenant; `persist_runtime_policy_design_case_graph` can write CAS bytes | production producer pipeline stores only `model_dump()` in its report; the persistence helper has zero production calls and no manifest output edge | `artifact_missing` |
| `policyos.layer2_s2.design_record_v0` | `persist_s2_design_search_run` can write the record and search ledger | persistence helper has zero production calls and no input/closure edges; `DesignRecordV0` has no run, case, tenant or job field and forbids production authority | `artifact_missing` |

The exact source anchors are `src/polisyos/core/run/context.py:411`,
`src/polisyos/core/run/manifest.py:18`,
`src/polisyos/runtime/http/services/control/run_lifecycle.py:1083`,
`src/polisyos/runtime/http/services/control/nl_pipeline.py:4242`,
`src/polisyos/runtime/quality/producer_pipeline.py:810`,
`src/polisyos/pdc/_impl/compiler.py:494`,
`src/polisyos/pdc/_impl/layer2_design_search.py:1393`, and
`src/polisyos/pdc/_impl/layer2_readiness.py:320`.

## Complete censuses and cross-checks

The primary census was an AST walk of all 5,579 tracked Python files. It
parsed every file with zero ambiguous files. It found:

| function | definitions | production calls | test calls |
| --- | ---: | ---: | ---: |
| `persist_runtime_policy_design_case_graph` | 1 | 0 | 1 |
| `persist_s2_design_search_run` | 1 | 0 | 6 |

The independent textual call census over the same complete tracked-Python set
returned the same seven test calls and zero production calls. A separate raw
byte walk of all 9,918 tracked paths had zero unreadable files and found the
runtime graph artifact kind only in its production definition and one test;
the DesignRecord kind occurred seven times across four files, with its only
source implementation in the persistence helper and its only executable call
sites in tests. These are occurrence and line counts separately; for both
literals every occurrence occupied one line.

Focused existing tests completed under a fixed 90-second ceiling:

```text
tests/unit/core/phase0/test_artifact_graph.py
tests/unit/runtime/http/test_runs_api.py::test_terminal_fact_requires_a_resolved_owner_manifest_ref
tests/unit/runtime/http/test_cycle_board_projection_loading.py::test_loaded_n13b_stays_control_plane_only_and_ds8_absence_has_no_value
tests/unit/pdc/test_runtime_policy_design_case_compiler.py::test_runtime_policy_design_case_graph_persists_as_runtime_artifact
tests/unit/pdc/test_layer2_s2_design_search.py::test_s2_persists_design_record_and_search_ledger
```

Result: `15 passed`. This proves the isolated CAS helpers and the current
typed-absent consumer behavior; it does not establish a production bridge.
C00 did not add a red positive resolver test because fabricating the missing
production closure in a fixture would test the forbidden mock-authority path.

## Inherited invariant receipts

- Generated-client census completed exit 0 in 21.149 seconds under a fixed
  90-second ceiling. Its complete candidate population was 1,377 tracked
  structured files (1,177 JSON and 200 TOML), with 18 primary and 18
  independently derived anchors, 34 construct identities, 2 recomputed
  absence predicates, 34 navigation hints, zero legacy line bindings and an
  empty error set. No generator ran.
- The DS5 ordered identity corpus test passed with 147 entries at
  `e297ac8da1a63c06ad9a1e15de760cdb347395900f14d59997bbf8e0af94d5da`.
- Independent Python and JQ recursive walks of
  `architecture/atlas_surfaces/status-retirement-inventory.json` agree on 383
  integer line-bearing leaves: `145 line + 103 start_line + 103 end_line + 15
  canonical_line + 15 schema_line + 1 current_inline + 1 ds1_inline`. The
  Python walk and an independent raw-occurrence scan both count 30
  `#ts-identity` references.
- The status checker completed exit 1 in 71.139 seconds under a fixed
  90-second ceiling, with uptime before/after. It emitted zero stdout lines and
  exactly 13 stderr diagnostics at SHA-256
  `511bfd68fea9232d15e33a577859121ca61501a4824a8535ccfd16551ffa17f9`.
  This is the expected inherited receipt; no diagnostic changed.
- A complete walk of 1,005 tracked dashboard TS/TSX files found
  `run_terminality` once on one line, only in generated
  `apps/runtime-dashboard/src/api/types.ts`; non-generated production
  consumers remain zero. C05 did not run and does **not** discharge
  `run-lifecycle-terminal-fact`.
- The protected Atlas and GY plan line-7 byte hashes are respectively
  `4c7438d5dd271de5c0020c32849771e8eadf2f5c936a58bf9806b126723ed684`
  and `ffe105ef594603c3a2a3a0247d41cb188529c4fd6fd72cab3ddfbde7956fc6e0`.
- The committed A4 expectation was not written or regenerated. Therefore the
  confirmed planning receipt remains the last A4 evidence; no composed-gate
  red-to-green, bounded derivation, or no-writer pair exists on this branch.

The deep-import baseline, DS6-C11 replay pin, DS5 run-deck visual delta, and
the 13 status diagnostics retain their existing owners. No composite
guardrail exit was used as a generated-freshness verdict.

## Cluster, round, and downstream state

| cluster | state |
| --- | --- |
| C00 | preflight complete through the canonical stop; no mechanism path changed |
| C01 | not entered; positive source cannot be resolved from a real run closure |
| C02-C08 | not entered |

Mechanism rounds consumed: **0 of 12**. This is the declared stop condition,
not a review finding or exhausted round.

Consequently there is no C02 two-family freshness receipt, no C07 145-path
register map/corruption battery, no C08 composed A4 gate, and no executable DS6
C13 conjunction. `adjacent-print-export` remains open, the C13 receipt is
absent, and no DS6 transition is claimed. C14 remains DS6-owned and this
journal makes no claim about its status. DS9 remains gated. No claim is made
for any of those deliverables.

The smallest owner re-cut is for `team-runtime`: a production producer must
persist the case graph and DesignRecord as content-bound artifacts in the
authorized core-run closure, give the DesignRecord run/case/tenant identity or
an equally strong verifiable binding, and expose declared closure roles. Only
then can DS8's planned resolver reuse the canonical run index, bound terminal
manifest loader, dependency graph resolver, and authority reconciliation
intake. A builder, global index, mock authority, or resolver-side scan remains
forbidden.

Read-only preflight also found later-slice cap companions that require owner
reconciliation after the producer exists:

- `team-frontend`: C05 needs `apps/runtime-dashboard/src/api/validators.ts`
  because the current run-summary validator strips `run_terminality`; the
  approved one-path C05 cap names only `RunsListPage.tsx`.
- `team-frontend` and the DS8 plan owner: canonical case/report routing and
  exact-byte prefetch require the existing route-manifest/query-key/loader/
  prefetch owners, which are not all in the approved C03/C06 path sets.
- `team-architecture`: the repository has no executable register-token or
  generated-family-token acquisition protocol; the user-supplied
  serialization rule remains the authority if execution is re-cut.

## Preservation and resource release

The OpenAPI/client token, Atlas register-family lock and visual-lane token were
never acquired. No server, writer, generator, snapshot writer, or fixed-port
process was started. The worktree index lock reads absent and was not touched.
Thus all three serialized resources are unheld; there is no token or lock to
carry across this stop.

The branch remains attached and is handed back in place. This journal must be
committed and then read back from the branch; the final receipt records that
commit and clean-tree state.

## DS8-A continuation — Revision 3.29

The owner accepted the `artifact_missing` stop at zero rounds and narrowed its
scope. DS8-A resumes the paper, support-rebind, run-terminality, register and
closeout clusters while `case-record-not-run-bound` remains a registered typed
unavailable owned by `team-runtime`. DS8-B alone inherits the case-inspection
endpoint, resolver, Case Workspace and MACHINE twin.

The attached branch advanced append-only to user-directed immutable base
`9e6a43b53d11166e90df376940cb34ff15b77289` through merge commit
`0a6e45645e21234c9c4b4a7cc8d5811e8e3056f2`. Independent complete Git
comparisons from `6049bf450c298885fa6b9077a144766b5fcd7c7a` to the new base
each returned exactly one documentation path:

```text
M policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
```

The reallocated mechanism budget is **nine rounds**, with C03's two rounds not
transferred and C01's paper-only scope halved:

| cluster | DS8-A scope | mechanism rounds |
| --- | --- | ---: |
| C00 | new-base bind, red tests and artifact-role preflight | 0 |
| C01-A | full paper contract, replay pins, href and typed unavailable case slot | 1 |
| C02 | OpenAPI plus both generated client families | 1 |
| C03 | DS8-B; not attempted | 0 |
| C04 | four support-only artifact/evidence rebinds | 2 |
| C05 | consume `RunSummary.run_terminality` without substitution | 1 |
| C06 | paper producer/consumer, egress closure and composed A4 gate | 2 |
| C07 | complete 145-production-path governed map | 2 |
| C08 | frozen closeout, two no-writer receipts and C13 handoff | 0 |
| **total** |  | **9** |

Opening spend is **0/9**. P40 remains binding: classify each finding before a
repair; on the second finding of one class, widen once or declare a bounded
residual with its falsifier; never add a third patch. Tests, this journal,
generated/release companions, governed register records and the one authorized
bounded snapshot derivation remain P39 record companions rather than mechanism
paths.

### C00 artifact-role preflight

The paper source denominator was walked before contract work. DS8-A admits only
facts already bound into the terminal run closure:

| paper role | admitted source | binding / negative |
| --- | --- | --- |
| run identity, terminal state and times | verified terminal `core.run_manifest` plus producer-owned `RunSummary.run_terminality` | the canonical bound-manifest resolver must re-check CAS bytes, sidecar kind/media/schema, run/tenant/cell identity, producer provenance and registry lineage; terminality is the exact `terminal` / `non_terminal` / `not_established` value and is never inferred from status |
| replay identity | manifest artifact id and schema plus a versioned paper-projection rule and recomputed projection hash | all pins are required together and recomputed; omitted, partial, mixed or mismatched pins fail with 409 |
| run stage trace | the verified manifest trace/provenance reference | this is the `#stage-trace` section of the run paper, never a case/DesignRecord stage or promotion claim |
| ordinary artifact links | exact manifest outputs with content-bound artifact identifiers | only admitted links are preserved; a valid zero-link packet emits no synthetic link |
| case / DesignRecord | no admitted run-bound source exists | the full ABI slot is `artifact_missing`, reason and closure signal `case-record-not-run-bound`, capability state `producer_missing`, owner route `team-runtime`, with a non-empty `may_not_use_for`; case values may not be built, mocked, globally indexed or borrowed from unrelated persistence |
| browser-local reviewer state and signed public targets | no admitted paper source | excluded from the packet and from every print/MACHINE egress |

This classification makes the available run-paper projection independent of
the unavailable case slot. A Cycle Board href is resolver-backed only when it
addresses the verified run-manifest paper projection and its complete replay
tuple. An unavailable or foreign-tenant run remains a typed absent href; a
mere string or guessed route is not an available fact.

### P40 property widening before source work

The earlier C05 validator omission is the first finding, and the C06
route/query/loader/prefetch bypass is the second finding, of one class: the
declared path set was narrower than the single-response typed-egress property.
DS8-A therefore widens this mechanism once and will not pay site patches for a
third example.

- C05 is **two** production mechanism paths: `src/api/validators.ts` preserves
  the producer-owned three-state value and `RunsListPage.tsx` consumes it.
- C06 is **eleven** production mechanism paths: one raw-byte paper hook, one
  pure paper presentation, one exact-byte export helper, the canonical query
  key, report loader, report prefetch, route manifest, runs route, report
  consumer, overview link-only consumer, and scoped print CSS.
- Tests, generated artifacts, package/lock and PDF helpers, the journal,
  register/inventory and bounded snapshot are mandatory P39 companions outside
  those mechanism counts.

The widening targets the property: one resolved paper response supplies the
typed DOM, print tree and byte-identical MACHINE download; `/report` is its only
emitter, while `/overview` can link/prefetch but cannot render or export its
payload. A later route or component instance of the same class folds into this
invariant and consumes no new patch round.

### C00 red receipts

`corepack pnpm install --frozen-lockfile` completed first, exit 0 in 1.7
seconds under a fixed 180-second ceiling, with no tracked delta. The focused
frontend red ran 27 tests in two files: 22 passed and five failed in 11 seconds
under a 120-second ceiling. The three validator failures prove Zod discards
each producer state, the negative proves missing terminality is accepted, and
the real-DOM failure proves the list renders none of them.

The corrected focused backend red completed in 17 seconds under a 60-second
ceiling: seven of seven tests failed for only the intended missing mechanisms.
Five `/paper` tests received 404/no OpenAPI operation, and the two Cycle Board
tests failed because `CycleBoardProjectionService` has no injected stage-trace
resolver. Both runs recorded an `uptime` pair and completed; these are red
receipts, not killed non-receipts. C00 changes no production mechanism and the
mechanism spend remains **0/9**.

## C01-A — frozen run-paper producer and Cycle Board bridge

The one C01-A mechanism round landed as the seven-path property declared by
the plan: strict frozen DTOs, one manifest-backed projection service, public
reuse of the existing bound-terminal-manifest verifier, one `/paper` operation,
the Cycle Board source-kind extension, resolver composition, and request-tenant
DI. `openapi_contract.py` and tests are P39 companions.

The producer requires exact owner `RunSummary.run_terminality == terminal`,
then re-verifies the manifest CAS bytes, sidecar kind/media/schema, run/tenant/
cell identity, producer/environment provenance and registry lineage. Trace and
ordinary output refs are separately verified against their sidecars before
they become paper facts or links. The projection carries no request clock,
browser state or signed target. Its semantic hash excludes self-referential
addresses and pins.

The full case ABI is frozen with an available arm for a content-bound
`DesignRecordV0`, separate grounding/admission/promotion facts and distinct
blocker/limitation/objection/abstention objects. DS8-A has no code path that can
construct that arm. Every emitted packet instead carries exactly the registered
`artifact_missing` / `producer_missing` / `case-record-not-run-bound` /
`team-runtime` typed unavailable, with all nine denied uses and no available
keys.

The available arm is not merely field-shaped. DesignRecord digest/ref/kind/
media/schema and case/record/run/tenant identities are structural invariants.
Each future authority or issue source carries content hash, schema, producer,
role, verifier id/version and verifier-bound case/run/tenant/record identity.
Grounding, admission and promotion use their closed owner vocabularies and
require distinct source artifacts and validators; a candidate admission cannot
carry governed promotion. The packet recomputes its complete semantic hash,
ordinary artifact hrefs derive from their refs, and hashes, pins and addresses
must agree.

Replay is zero pins for the current packet or exactly all four recomputed pins.
The HTTP boundary walks raw query multi-items before FastAPI can collapse them:
unknown or duplicate keys in either order return 422, as does malformed syntax;
well-formed partial, stale and cross-generation tuples return 409
`run_paper_replay_conflict`. Complete replay returns byte-identical HTTP content.
The report href serializes all four pins before `#stage-trace`. Cycle Board only
emits that href for a non-`None` tenant-bound resolver result and adds its
manifest id and projection hash to the composition manifest; changing the paper
hash changes both board composition and projection hashes.

P40 classified raw-query scalar collapse and stale semantic-content replay as
the first and second findings of one replay-identity class. The mechanism was
widened once to the whole raw-multiset plus semantic-content property. A stale
unavailable-to-available substitution now fails on semantic hash recomputation,
while an independently recomputed available packet passes; wrong source role,
verifier identity and derived artifact href each fail their own invariant. The
remaining declarative verifier/content proof is a bounded DS8-B residual: only
the registered run-bound producer/resolver can establish those source bytes,
and DS8-A's emitter has no available-arm path.

Final measured greens, each with a fixed ceiling and `uptime` pair:

- paper API, real-CAS corruption, raw replay syntax, semantic binding and strict
  OpenAPI union: 8 passed, 11 seconds / 60;
- resolver/Cycle Board link and composition hashing: 2 passed, 8 seconds / 60;
- global runtime OpenAPI examples/problem hardening, including independent
  paper-example hash recomputation: 18 passed, 28 seconds / 90;
- focused Ruff over all C01-A and companion paths: clean.

The worktree-local `.venv` did not contain Ruff, so that first static-check
attempt was a tooling non-receipt; the repository environment's Ruff module ran
the exact path set clean under the same 60-second ceiling. Three final
delta-only reviewers returned GO: API/OpenAPI, authority/content binding, and
focused behavioral tests. The last reviewer independently completed the
combined 28-test set and reproduced both stale-swap rejection and recomputed
available acceptance.

The real-CAS negative first obtained the packet, changed the exact manifest
blob while preserving its id/ref/shape, and then proved both the HTTP producer
(409 `run_paper_source_invalid`) and direct stage-trace resolver (`None`) fail
closed.

A broader Cycle Board/API replay returned one unrelated red: the raw governed
owner packet was `invalid_source` where an existing test expects `available`.
P41 replay from an archive of immutable slice base `9e6a43b53` reproduced the
identical assertion in 20 seconds / 90. The failing subpredicate reads the
unchanged `services/governed_projections.py` definition, owner JSON and owner
validator; C01-A's route DI and composed-paper additions do not enter it. It is
therefore an inherited completed red, not a C01 repair or stop.

C01-A mechanism spend is **1/1**; cumulative spend is **1/9**. The
`case-record-not-run-bound` producer gap remains owned by `team-runtime` and no
DS8-B route, resolver or workspace was attempted.

At the continuation bind, all three serialized resources were unheld. The
protected line-7 byte hashes are Atlas
`74cd4a8823318ffb00c349d05e19c7d8413b2123a6bd5c15ab88f291a837aebf`
and GY
`ffe105ef594603c3a2a3a0247d41cb188529c4fd6fd72cab3ddfbde7956fc6e0`.

## C02 — generated paper clients

The regeneration token was acquired once after the C01 freeze. Two setup
attempts were tooling non-receipts (`fastapi` absent from the worktree venv;
then `tools` absent from `PYTHONPATH`) and changed no generated output. With
`PYTHONPATH=src:.` and the repository environment, the OpenAPI export completed
in 7 seconds / 60; both generated TypeScript families then completed in 3
seconds / 60. Generated outputs were never hand-edited.

The first architecture receipt found four DS8-owned imports below the stable
facades. One convergence repair replaced terminality and artifact internals
with the owner literal and `polisyos.core.artifacts` facade; focused paper tests
(8 passed) and Ruff were clean. A final derivation then reported both actual
GY-DEF20 predicates clean: runtime-api-client **5/5** generator-observed outputs
and runtime-dashboard-api-types **1/1**. The composite remained red only for the
six inherited `deep-import-baseline-stale` edges; no DS8 path appears in that
denominator and `guardrails sync` was not run.

The independent generated-client census walked 1,377 JSON/TOML candidates and
returned 18 primary plus 18 independent anchors, 34 construct identities, two
absence predicates, zero legacy line bindings and zero errors. C02 spends
**1/1**, cumulative **2/9**. The regeneration token was explicitly released
after these predicates were read back.

### C04 P40 classification before repair

The first delta review classified the surviving SLA-colored thread bar and
governing container as **SAME-CLASS-DEEPER** local authority clothing. C04-R1
therefore widens once to the complete local-SLA presentation property: neutral
geometry and labels with explicit interaction-purpose/display-state metadata.
It does not invent `ProjectionFreshness` or claim the registered authority
rows closed.

The final C04 review classified the new accessible 0–100 meter as a **NEW
P38/P15 proxy class**: the clamped decorative width is not a producer quantity.
C04-R2 removes that invented measurement, marks the bar decorative and keeps
only the interaction labels semantic. This exhausts C04 at **2/2**.

C04 red was 4 failures / 10 passes; green is 14/14 across the four support
views, targeted ESLint and dashboard typecheck clean. Final read-only review is
GO. No route, field, MACHINE view, or authority-debt closure is claimed.
Cumulative spend is **4/9**.

## C05 — run terminality consumer

P40 classifies the page-only omission as **SAME-CLASS-DEEPER** content
preservation, already widened in C00 to one ingress-plus-consumer mechanism.
The generated `RunTerminality` union now validates exhaustively at Zod ingress;
the list renders and exports that exact field in neutral clothing, never status
or Cycle Board substitution.

The focused validator/hook/fixture/page wave is 33/33; the two P15 files remain
12/12; targeted ESLint and dashboard typecheck are clean. A complete UTF-8 walk
of 984 tracked dashboard `src` TS/TSX files (zero ambiguous) and independent
`rg` occurrence census agree: production has three occurrences/three lines in
exactly two paths—validator (one) and RunsListPage (two)—beside two generated
and 15 test occurrences. Thus C05 discharges `run-lifecycle-terminal-fact`.
C05 spends **1/1**, cumulative **5/9**.
