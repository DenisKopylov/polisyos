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

At the continuation bind, all three serialized resources were unheld. The
protected line-7 byte hashes are Atlas
`74cd4a8823318ffb00c349d05e19c7d8413b2123a6bd5c15ab88f291a837aebf`
and GY
`ffe105ef594603c3a2a3a0247d41cb188529c4fd6fd72cab3ddfbde7956fc6e0`.
