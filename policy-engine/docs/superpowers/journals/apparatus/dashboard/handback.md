# Dashboard apparatus contribution

Implementation follows `docs/superpowers/specs/2026-09-10-apparatus-dashboard.md`
at Stage 1 commit `e4b9ce4dfe7ebcafa111582e3da3a8f3bbdba8dd`. Root integrates commits
and owns final cold-station/full-suite receipts. This is a contribution, not a
completion claim. Raw paths below are relative to this directory.

## B1 — unavailable child execution

`persistenceProcessResult.ts` now emits named `PersistenceExecutionUnrunError`
with `UNRUN:` for launch failure, signal/timeout, absent output and malformed JSON.
It preserves the actual cause/stderr and leaves deliberate nonzero JSON refusal
status/body unchanged. No deadlines changed.

| Gate | Exit | Measured duration | Complete output |
| --- | ---: | ---: | --- |
| Exact decoder file before implementation | 1 | Vitest 3.19s | `raw/decoder-unrun-red.log@1d68c5d5b978ebd644dd2648886861b8cd1be3cb823291ceb048c39a9a64137a` — four failed, two passed |
| Same decoder file after implementation | 0 | Vitest 5.12s | `raw/decoder-unrun-green.log@2bbcb440b64974d727f2deb39400c417b9de4146635fe6719bcd000a4fd87dd7` — six passed |
| ESLint two changed decoder files | 0 | Tool session elapsed not emitted after redirected async completion | `raw/decoder-lint.log@e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The tests execute real failed, missing and timed-out children. The deliberately
refused JSON envelope remains a separate passing case. Prettier formatted only
the two changed files (`raw/decoder-format.log@930c52477fc6047501474d44ba61df60078472c9c951c5f7b17d8377e0f06710`, exit 0).

## B2 — station binding and hook dispatch

The existing process module selects the checkout-relative `.venv/bin/python`
without PATH fallback or realpath collapse. Automated Core capture, workflow
source-flip replay and the public capture bridge use it. Workflow now emits a
completed JSON result; the shared decoder distinguishes unavailable execution.
Health and readiness producer owners compose that decoder without changing
canonical admission or typed refusal semantics. The readiness control is produced
under the Python admission owner's actual `_trusted_node()` selection, then
independently admitted; claimed path/hash/version tampering still fails.

| Gate | Exit | Wall time | Complete output |
| --- | ---: | ---: | --- |
| Ambient Python consumer replay before repair, 2 failed / 19 | 1 | Vitest 7.96s | `raw/python-consumer-path-red.log@f59d8482fa832711b1d188c7dd7741fa6e8ac70b01aa474ad4908709e3e5fd99` |
| Identical two consumer files after repair, 19 passed | 0 | 8.37s | `raw/python-consumer-path-green.log@30312b870c2ca203d92fa4ff17f656147d74fc0b6c2c83118121d6a5f9dba2e4` |
| Locator/decoder/capture/workflow, 27 passed | 0 | 9.92s | `raw/python-locator-green.log@4a76a96636df2ee3dbb46f892789a1a8411bbefd488bf7de5bb3e1a37f0ae9fc` |
| Both producer owners: missing interpreter/dependency/non-JSON, 6 failed before repair | 1 | 2.99s | `raw/producer-unrun-complete-red.log@022793f30ebddf9f3b009dde4aa91905319dbd2356564d4703ef2e648dde60f3` |
| Both producer owners plus decoder/locator, 14 passed | 0 | 4.44s | `raw/producer-unrun-green.log@b64031eb21297ade9fa4958310e29a1eaf67df72f700bd54a811d8da30c28594` |
| Alternate Node binary path before canonical fixture repair | 1 | 12.57s | `raw/readiness-alternate-node-bound-loader-red.log@9c73defa59a8c6952c2c68e53f5dc310229b1ba4448f1378e50ede886fb1446b` |
| Same alternate Node invocation after repair; includes 3 provenance refusals | 0 | 21.08s | `raw/readiness-alternate-node-green.log@afa80714274b5c485e0b5dbba46c12ae03e039bf095f7c89fd5b299f082691d6` |
| Installed hooks, 12 passed including 4 pre-push cases | 0 | 11.26s | `raw/hook-prepush-behavior.log@8cb618815ee25b661f636a5134de07b787ff16ff14c98510bed2d01e696339b3` |
| Hook test Ruff | 0 | 0.04s | `raw/hook-lint.log@691193803502a54d30119efb3abec47796d6478e9adbca3974305886b7c81144` |
| Frozen six evidence files, 95 passed | 0 | 77.90s | `raw/dashboard-evidence-final.log@adea8298406890f7f6f6bfce8b2fe711b63a5c9135cb321150fba6d87df60941` |
| Final producer diagnostics plus existing cause-preservation test, 7 passed | 0 | 3.90s | `raw/producer-diagnostic-final.log@1633db0dfa49b9686890528e1e7cff170b605601761c2494b90295e7aca3b6e8` |
| Final ESLint, all 11 touched TS/config paths | 0 | 20.32s | `raw/dashboard-lint-green.log@010e689dcdf72919e943b7ad24bf6360bacf2174a20222a5b51903c9542e0ee3` |
| Dashboard typecheck | 0 | 18.11s | `raw/dashboard-typecheck.log@0f66e8a4bc3496a2cd0256010bae1804e1f1082d6e924fbb6b564600d7b9e14a` |

The hook tests invoke the installed `.git/hooks/pre-push` directly from repository
and dashboard CWDs. Typecheck exit 0/29 propagates; an unselected suite would exit
73. No push occurred. Existing lefthook, package and CI lane policy is unchanged.

## B3 — native accessibility measurement

Decision addendum committed/read back at
`efd515851ae6f8ab98b5d91cdc81f34548914345` before migration. The same test now lives
in `ConfidenceLedgerRiskSpend.a11y.browser.test.tsx`, runs in the existing
confidence-ledger Chromium project, imports the same OpenAPI example, and uses
already-declared `axe-core`. Both zero-violation assertions and the 30,000ms
watchdog remain. Standard `test:coverage` still includes it. Attachments are
routed to ignored `_build` output.

| Gate | Exit | Wall time | Complete output |
| --- | ---: | ---: | --- |
| Original exact-file coverage timeout | 1 | Vitest 47.31s | `raw/a11y-targeted-baseline.log@14da1dc987a6ee943bc11ea0fc08529bcedc4e9d209785373bc1c62192c9d5f5` |
| Same component/axe calls instrumented in JSDOM: 14.595s + 11.877s | 0 | Vitest 33.65s | `raw/a11y-timing-probe-bound-deps.log@f61c953a89f7cd637767a58b1ebdeb324d1b5b5cb1c5b4bfd08145a64cb3d25e` |
| Native Chromium positive scratch control | 0 | 5.31s | `raw/a11y-browser-native-axe-probe.log@dfda59b9908c756df7e4d34f742406c165b3427eead20630ec9ee16b62fee570` |
| Remove actual dialog accessible name; zero-violation assertion rejects `aria-dialog-name` | 1 | 6.37s | `raw/a11y-browser-dialog-name-negative.log@a8b569e61336ee517684ea828bc46886264fbd7a0160d57c968f7d63e22486d1` |
| Migrated test plus existing browser twin owner, 74 passed | 0 | 62.71s | `raw/a11y-browser-owner-green.log@f892c189befdd2202d1802f3462072ac27fa7573b202279c22175583793729d6` |
| Migrated exact file via standard projects with coverage, 1 passed | 0 | 8.72s | `raw/a11y-browser-coverage-green.log@6d62ce0b66d8f8f99a05b1348351602d6f25f17beabe7311895dafe5c4e38dae` |

## Routed limitations and non-receipts

- NEW class, explicitly bounded source-list provenance: capture's existing
  implementation hash binds its five declared paths, not their transitive imports.
  This repair does not widen that artifact contract. The shared execution helper
  is outside the list; canonical bridge payload/CAS admission remains independent.
  A stronger dependency-closure claim needs the provenance schema/producer/consumer
  owner to extend the declared set. Root accepted this route rather than a new
  artifact contract in this apparatus repair. The actual Python provenance owner
  was run against fixture copies, then the helper was replaced with an incorrect
  interpreter selector: its bytes changed while the five-path aggregate stayed
  equal. This confirms the bounded residual (`raw/capture-provenance-bounded-residual.log@f5e411bc92897aa3e26b609706de4e34f897bb35ac30ea94336ad632d190c7cc`,
  exit 0, 0.76s); no transitive-closure mechanism exists in that owner.
- Initial browser probe importing Node-only `vitest-axe` was an UNRUN station
  mismatch (`raw/a11y-browser-probe.log@f4f167f3208cda298eb3792de840799c525adb9c8e02bb2845c3187b56cbd413`); native `axe-core` closed it. Initial
  timing probe lacked scratch React binding (`raw/a11y-timing-probe.log@8c21d18cd29b35bf5f2f4923454974268263df9f9c4d18a855ae51079975e172`), and
  initial alternate Node copy lacked its dynamic library
  (`raw/readiness-alternate-node-red.log@90785bdfe96c1250d8e07dfff203b84ae4b6243cabda25c153694d19834e2edd`); these are setup non-receipts.
- `raw/capture-public-bridge-green.log@584322e88f44f918b8c6ecbd8ace219157125d2f6e696d6fceb2d865928130ff` is misnamed: exit 1, 2.83s. My own
  formatter overlapped its measured source and triggered a Core provenance
  refusal; it is invalid as a stable-source verdict. The frozen final exact-file
  replay below replaces it. The newly added public capture/CAS assertion itself
  passed in that run; no product defect is inferred.
- Final root owns clean detached worktree provisioning, empty caches, two-CWD
  repeated complete-suite/ratchet verdicts, and closure. Remote CI is not claimed.

## Final exact invocation and review boundary

From `policy-engine/apps/runtime-dashboard`, frozen evidence regression:

```sh
corepack pnpm exec vitest run src/test/evidence/persistenceProcessResult.test.ts src/test/evidence/evidenceProducerExecution.test.ts src/test/evidence/atlasAutomatedEvidenceCapture.test.ts src/shared/lib/domain/workflow.test.ts src/test/evidence/atlasHealthMetrics.test.ts src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000
```

Final accessibility coverage invocation from the same CWD:

```sh
corepack pnpm exec vitest run src/features/runs/components/ConfidenceLedgerRiskSpend.a11y.browser.test.tsx --coverage --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000
```

After the 95-assertion run, the only source edit replaced one conditional test
expectation with an equivalent unconditional expectation for ESLint. Its exact
file and the existing error-cause owner test were replayed: seven assertions
passed. No additional mechanism edits followed. Pattern register reread before
handback: P29 real-path falsifiers, P31 three Python consumers plus producer
siblings, P38 explicit station/property distinction, P40 bounded provenance
scope, P41 no unsupported inherited-red claim. Root performs independent review
and committed-byte readback. No debt register or ledger edits were made.
