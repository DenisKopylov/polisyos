# Measuring apparatus completion journal

Status: local apparatus work complete. Repeated cold measurements now reach
artifact verdicts or explicit UNRUN. The dashboard's unchanged coverage ratchet
returns the same **completed rejection** in both directories; coverage adequacy
and unexecuted hosted CI remain routed limitations, not green claims.

## Custodied source and sequencing

Work is local on attached `codex/measuring-apparatus` in
`/Users/deniskopylov/polisyos/.worktrees/apparatus`, based on
`c49449343cbaa8dfeba9d0c7afd3de67355205a3`. No push, rebase, reset or storage stash
was used. The architect's debt register and ledger were not edited.

The first commit, `4de45d2b51fe54a7f81bc1a8351d59714bcfd182`, only added the
requested ignored raw-receipt path. Stage 1 was committed at
`e4b9ce4dfe7ebcafa111582e3da3a8f3bbdba8dd`; every decision's complete committed bytes
were read back from the attached branch before source changes. The decisions are:

- `docs/superpowers/specs/2026-09-10-apparatus-architecture.md@e4b9ce4dfe7ebcafa111582e3da3a8f3bbdba8dd`.
- `docs/superpowers/specs/2026-09-10-apparatus-dashboard.md@e4b9ce4dfe7ebcafa111582e3da3a8f3bbdba8dd`.
- `docs/superpowers/specs/2026-09-10-apparatus-station-and-ci.md@e4b9ce4dfe7ebcafa111582e3da3a8f3bbdba8dd`.

The browser-station addendum was committed/read back at
`efd515851ae6f8ab98b5d91cdc81f34548914345`, before migration. The native mutation
boundary addendum was committed/read back at
`5b98095ea73eefc88fb0c587ef20da267b55744d`, before its preflight guard.
Each decision names composed owners, untouched seams, shared-file effects and
row-specific behavioral falsifiers. Root serialized commits, dependencies,
workflows and architecture changes; the three workstreams shared no mutating
owner during their deciding measurements.

The final source freeze is **`272d3bbc4cf7fcefe51a76ef78869064557eeaa9`**. A new
detached checkout at that exact commit, `.worktrees/apparatus-cold`, supplies the
closure measurements. Later journal-only commits do not change that measured
source. Paths below are relative to `policy-engine/`, except `.github/**` and
`.gitignore`. `A/`, `B/`, and `C/` abbreviate this journal directory's
`architecture/raw/`, `dashboard/raw/`, and `station/raw/`. Every cited raw file is
local and ignored; hashes identify the retained complete output, not a tracked
copy or a replacement for the gate's observed exit status.

## Eight register rows

| Register key | What failed to be measured | Disposition and deciding evidence |
| --- | --- | --- |
| `isolated-freshness-probe-cannot-build-its-own-interpreter` | **Check never ran.** A copied managed Python executable aborted loading `libpython3.14.dylib` before a generator. | Repaired by composing `uv venv --python <active interpreter>` with the existing private frozen sync/copy owner. Actual private interpreter and fixture-import probes, followed by the cold complete freshness pair, establish execution. See A1 and the cold matrix. |
| `architecture-freshness-gate-hides-generated-artifact-drift` | **Check never ran**, but its absence entered the ordinary, waivable findings set. | Repaired with separate typed UNRUN aggregation and exit 2. Successful siblings retain actual drift; incomplete siblings cannot establish freshness. A valid waiver previously turned unavailable measurement green; the red probe and repaired real-child negatives establish the distinction. Cold normal and offline pairs establish repeated pass0 versus UNRUN2. See A2. |
| `evidence-tests-launch-python-that-the-station-does-not-provision` | **Wrong station**, causing setup/collection not to run: installed dependencies belonged to a different Python. | Repaired at the existing shared process owner. Three bare-Python consumers now select checkout `.venv/bin/python`; health/readiness producer siblings distinguish unavailable execution from completed refusal. Actual child persistence, source-flip, poisoned-PATH and malformed/failed-child probes pass. Final full-suite pair establishes cold execution of the evidence suites. See B1. |
| `pre-push-hook-runs-the-suite-in-a-configuration-ci-never-uses` | Historical **wrong station/configuration**: a different local suite policy. | Already repaired at the slice base: pre-push is typecheck-only. No hook configuration change was needed. Actual installed hook runs from both cold directories select only the declared three TypeScript projects and exit 0; controlled real-hook tests propagate typecheck failure and reject accidental suite dispatch. No push occurred. |
| `dashboard-unit-suite-has-fifty-failures-nothing-was-running` | Historical **check never ran**; reached failures must be classified individually. | The full declared coverage measurement is the deliverable, including an honest artifact rejection. Its properly provisioned baseline reached one accessibility timeout, not the historical 50-failure set. The same unfiltered assertions now run in the existing native Chromium project, with the same deadline. Full cold pair and the unchanged ratchet results are recorded in B2 below. |
| `gen-schema-check-red-on-main` | **Check never ran** in a job shadowed by unrelated prerequisite failures. The local check, once run, found real reference drift. | Repaired scheduling through an independent schema-snapshots job; aggregate requires its actual success. Existing canonical owner regenerated the stale IR reference. All required computation failures now emit UNRUN2; completed drift remains exit1. Cold full scans pass identically from both directories. See A3. |
| `odfpy-core-dependency-is-sourced-from-a-non-canonical-index` | **Wrong supply source/station trust posture**; ingestion could run, but depended on a noncanonical host. | Already repaired in source at the slice base by a locally pinned wheel. Reverified all 34 `odf/**` files against canonical PyPI sdist, cold installed the lock and executed a real ODS consumer twice. A valid modified wheel with unchanged lock is rejected by uv hash validation. No new dependency source was introduced. |
| `ci-red-inventory-on-20082e545` | **Mixed row**, decomposed into executed artifact failures, wrong stations, never-run checks, and event exclusions. It cannot honestly receive one binary station classification. | Triage complete in C-CI finding IDs; station defects repaired where established. Product failures remain individually routed, and cancelled/skipped hosted jobs have no verdict. This is not a claim that historical or current aggregate CI is green. Mutation and canary evidence/limits are recorded in C1/C2. |

### A1–A3: actual measurement, not a successful constructor

The complete manifest census at the slice measured 110 families; the default
selection is four families and eight declared output files. The selection was
not reduced. The optional heterogeneous `--all-generated-checks` protocol remains
outside this bounded repair; it has no common producer-completion contract.

`tools/devx/architecture/guardrails.py@272d3bbc4cf7fcefe51a76ef78869064557eeaa9`
retains existing artifact findings separately from `UnrunGeneratedCheck` and
`GeneratedArtifactCheckUnrunError`. Per-family station/producer failures continue
the successful siblings, but overall unavailable required measurement exits 2.
The orchestration boundary also classifies unexpected computation exceptions as
UNRUN, including a real zero-exit child emitting non-decodable bytes. An explicit
skip prints its limitation and never claims the skipped measurement passed.

Client generation composes the already locked dashboard `openapi-typescript`
through `corepack pnpm --dir <checkout>`, using copied input. Real poison binaries
for ambient pnpm/npx fail the pre-repair tests; the repaired producer emits the
same bytes from both outer directories. No network-selected generator was added.

The first working default check found an actual OpenAPI snapshot drift while
the other three families matched. This is not comparable to the previous
preparation-failure finding: the classes do not overlap. The owner was run after
source freeze; only its ten emitted hash/count fields changed. The existing
confidence owner was independently exercised across its complete 6,411 bindings:
no raw/journal path, no owner issue, no mid-run tracker issue. Product provenance
was not weakened to accommodate receipts.

`tools/quality/diagnostics/gen_schema.py@272d3bbc4cf7fcefe51a76ef78869064557eeaa9`
retains full comparison semantics and wraps required computation, not just one
schema import. Direct/nested Pydantic hooks, required imports, an empty required
catalog and reference production failures are UNRUN2. Actual schema/reference
drift is completed rejection1. The canonical reference producer repaired the
observed drift. `.github/workflows/abi.yml` now schedules schema snapshots without
an unrelated predecessor; actual aggregate-shell tests reject skipped/missing/
cancelled schema execution. The PR ABI compatibility job remains distinct.

| Deciding output | Exit / meaning | SHA256 |
| --- | --- | --- |
| `A/baseline-private-probes.log` | 1; real interpreter loader failure | `d32fd05fde3248729df9f4bb7ef48798ab82a5584c8b1be728d401c9de73948d` |
| `A/red-unrun-cli-valid-waiver.log` | 1; test exposes old unavailable-check waiver returning success | `ba10bc570abf7651af89db3166785e4f83bd672e44a25e7224c84ea23ed383ab` |
| `A/client-station-red.log` | 1; actual poisoned ambient producer | `9066c9e0d96e41fdc20124f7487b7b7c72487eaf524a812cf29f33caa121e514` |
| `A/client-station-green.log` | 0; real checkout-bound production | `99db33d5c94c6f7da021687c7391181685cc33299c5435b1c861e2db3be3ec87` |
| `A/real-default-after-station-repair.log` | 1; completed OpenAPI artifact drift | `74686161bf9dc13c58a435c92620806429b0140ebc25d5fe477f73c72bfcaf03` |
| `A/baseline-schema.log`, `A/baseline-schema-root.log` | 1/1; identical real IR-reference drift | `5b0db0c49382774d85f3941c7064e0f956a6778ded0ff723e9c8ed38208983ec` |
| `A/unexpected-measurement-red.log` | 1; non-decodable real child escaped the narrower boundary | `5b61818a4f39690b5353febe28c7880c7ed8fc31e8348763533872b93e23053f` |
| `C/schema-producer-boundary-red.log` | 1; five producer exceptions before widening | `17ddf28301fecac5b5cfcf07cb9a68fa1a3f0b153c919522a8b851510f5d32c6` |
| `A/measurement-boundaries-green.log` | 0; 27 explicit boundary cases | `a82a0b51cd86fa0131904e08c34ef556963104f0e3677f688117e093ebf2d3fe` |
| `A/root-exact-regression.log` | 0; 31 explicitly selected cases | `1b8f208de3636df279448e40805982570c4351601ce5723301928feea7d343cf` |

The 27-case command is `.venv/bin/python -m pytest -q` with these exact
arguments, all under `tests/repo_quality/tools/`:

- `test_architecture_phase3.py::test_non_decodable_generator_output_is_an_unrun_measurement`.
- `test_architecture_phase3.py::test_failed_generator_is_unrun_and_cannot_admit_partial_output` (both declared parameter cases).
- `test_schema_station_independence.py`.

The earlier 31-case command is the same executable with these explicit arguments:

- `test_architecture_phase3.py::test_generated_probe_refuses_unprepared_project_environment`.
- `test_architecture_phase3.py::test_failed_generator_is_unrun_and_cannot_admit_partial_output`.
- `test_architecture_phase3.py::test_guardrail_cli_cannot_waive_an_unrun_required_measurement`.
- `test_generated_client_station.py`.
- `test_schema_station_independence.py` (before the five later producer-hook cases).
- `test_schema_snapshot_workflow.py`.

Their recorded output is not represented as a whole-directory test result.

### B1–B2: dashboard reached verdicts

The red/green child, canonical Node provenance, actual installed-hook, browser
accessibility and negative-control commands/hashes are retained in
`docs/superpowers/journals/apparatus/dashboard/handback.md@272d3bbc4cf7fcefe51a76ef78869064557eeaa9`,
findings B1–B3. The frozen six explicitly named evidence files produced 95 passing
assertions, including real Python health/readiness execution. Deliberate authority
refusals remain refusals; inability to launch/complete a child is named UNRUN.

The full provisioned pre-migration baseline finished in 1,291.51 seconds:
405 files (1 failed, 403 passed, 1 skipped), 1,792 tests (1 failed, 1,789 passed,
2 skipped). Its complete output is
`B/baseline-provisioned-coverage.log@913987bdfb7b75fa675d36adbb52a9d3d3545bb12df7a46a02246526ea185946`.
The failed identity is
`ConfidenceLedgerRiskSpend accessibility > has no violations in the ordered reviewer surface or full-envelope dialog`.
The JSDOM axe calls approached/exceeded the unchanged watchdog. Native Chromium
measures those DOM properties promptly. Both unfiltered zero-violation assertions,
the same component/example and the 30,000ms test deadline remain; removing the
actual dialog accessible name makes the migrated assertion fail
`aria-dialog-name`. There is no test exclusion or ratchet relaxation.

Both final cold runs completed with the identical full population:
**406 files = 405 passed + 1 skipped; 1,802 assertions = 1,800 passed + 2 skipped**.
The original three CI failure identities and the migrated accessibility assertion
all passed. No file collected zero assertions. Vitest's JSON file status labels
the all-skipped file “passed”; the comparator separately enumerates its skipped
assertion, and this journal uses the terminal's accurate file disposition.

The exact suite flags are `vitest run --coverage --maxWorkers=1
--testTimeout=20000 --hookTimeout=20000`, with default and JSON reporters added for
complete identity comparison. The package script's exact following
`node ./scripts/check-coverage-ratchet.mjs` ran separately as the sole command only
after suite exit 0; this preserves its `&&` dependency and records both exits.
No coverage tolerance override was used. The complete absolute commands and
provisioning origins are retained in
`B/cold-dashboard-verdict.json@783284e5cf9ffb542b59a42a4a128715ae891ed778e4bebd0a97c0098a5f7c25`.

| CWD | Suite / wall seconds | Ratchet / wall seconds | Combined declared verdict |
| --- | --- | --- | --- |
| ROOT | 0 / 619.96 | 1 / 0.26 | **1, completed coverage rejection** |
| PRODUCT | 0 / 601.52 | 1 / 0.25 | **1, completed coverage rejection** |

Every test identity/status multiset, every file's coverage metric, every
statement range and every statement's hit-versus-unhit state match. The complete
coverage denominator is 281 instrumented source files. Statements are
**7,047/8,277 = 85.13%**, below the unchanged **85.57%** floor. Lines, functions and
branches exceed their enforced floors. The two coverage summaries are
byte-identical at
`453a5db937830c9811fbc0d8782e49205d885e6c7e91e0c74c4e75f823b1bee9`.
The full comparison exits 0 and is retained as
`B/cold-two-cwd-comparison.log@799d24451ac3de988185be8f594f0a5ff91d83ed5131492447ea84aa88349628`.
Both complete logs were checked for tracebacks, fatal Python errors and missing
modules; none occurs. React test warnings are retained, not silently filtered.

The two pre-existing skips are explicitly outside positive execution claims:

- `src/features/evidence/components/CapabilityDiscoveryPanel.free-growth.test.tsx`:
  `DS10 capability discovery free growth renders the owner-index result without a dashboard identifier branch`.
- `src/features/runs/export/confidenceLedgerRiskSpendTwin.test.tsx`:
  `confidence-ledger risk-spend production twin produces an exact native Chromium receipt and restores focus and every scroll position`
  (its existing native Browser Mode counterpart is selected and executes).

Complete test/coverage JSON and stdout are retained as
`B/cold-repo-cwd-suite.{json,log}` and `B/cold-product-cwd-suite.{json,log}`;
complete ratchet outputs are the corresponding `*-ratchet.log`. All hashes are
in the master receipt above. No full output is embedded in tracked documentation.

The statement deficit is a **new completed coverage-adequacy finding**, not a
measurement-unavailability excuse. Source-range inspection finds real unexercised
handlers and mocked capability paths. The retained JSDOM accessibility-only map
and final mixed-project map differ by 21 covered statement ranges; that bounded
comparison does not establish migration causality or a complete pre-change
baseline. Historical ownership remains `not_established`, because a full baseline
coverage report is unavailable and changed tests/config intersect the measuring
inputs. The ratchet remains red and routes to frontend coverage/surface owners.
The apparatus row closes on a repeatable artifact verdict; the product coverage
requirement does not close.

### C1–C2: CI inventory and supported stations

The complete historical jobs and failed logs for five exact runs were read, with
their artifact payloads. C-CI in
`docs/superpowers/specs/2026-09-10-apparatus-station-and-ci.md@272d3bbc4cf7fcefe51a76ef78869064557eeaa9`
routes every item under `CI-F01–F26`, `CI-S01–S16`, `CI-R01–R20`, `CI-B01–B06`,
and `CI-C01–C02`. These IDs mix job states, finding classes and individual subjects;
their sum is not a job count or failure count. Raw log/artifact hashes are in
that decision's receipt section. Its historical package JSON contains 243
findings, reconciled as `21+2+185+3+13+5+1+4+8+1`; the source register's abbreviated
ratchet account was not treated as the denominator.

The mutation owner now uses pinned mutmut 3.5.0's actual console entrypoint and
configuration, isolated scope/context, generated AST mutant identities, complete
per-mutant exit codes, selected executed-test identities and reconciled official
summary. It emits persisted pass0/fail1/UNRUN2; zero/missing/incomplete outcomes and
pytest internal error 3 cannot count as killed evidence. Existing Foundry 70% and
Scientist 80% floors remain; the release subset preserves its existing no-floor
semantics. The release workflow composes this owner and uploads its receipts/logs.

Native CPython 3.14 Darwin arm64 remains explicitly unsupported: actual repeated
runs showed intermittent post-fork setproctitle crashes before pytest, even after
one apparent successful workaround. The guard returns UNRUN2 before fork. This
is a bounded inability to execute that pinned engine on this native station,
not a claim that mutation testing is unavailable on the laptop. Root started the
installed Docker engine and provisioned a separate Linux station; this supersedes
the earlier contribution's time-bound `verification_missing`/daemon observation.

The Linux station is official `python:3.14.3-slim` at digest
`sha256:5e59aae31ff0e87511226be8e2b94d78c58f05216efda3b07dbbed938ec8583b`,
with pinned uv 0.9.21 and a frozen sync of lint/test/mutation. Its initial private
`.venv` and cache were empty. Docker mount inspection proves source `/repo` is
read-only; private volumes hold environment/cache/build outputs. No macOS venv or
site-packages are shared. The initial station probe's `repo_readonly` field tested
file mode, which does not establish mount writability; that field is a harness
non-receipt, superseded by the actual mount inspection (`linux-mounts.json`).

The same four exact test nodes run from Linux `/` and `/repo` with the identical
absolute Python/pytest arguments. Docker's `--workdir` is the transport's CWD
selection, not a measurement argument change. Both outer gates return 0; actual
persisted outcomes match as a complete set: strong test kills 2/2 mutants and
passes0; weak test leaves 2/2 survivors and fails1; failed clean baseline and
zero-mutant source each produce UNRUN2. The expected child traceback in both logs
is the deliberate clean-baseline `assert 4 == 3`, consumed as UNRUN; it is not an
unexplained station traceback. No native crash or skipped real-engine case occurs.
Complete child logs, generated metadata and four receipts per run remain under
`C/linux-{root,product}-fixtures/`.

Full gate output hashes are
`C/linux-mutation-root.log@3adb66551c9c17c3841a675e00271d9848b673454003007461680edd607d2a89`
and
`C/linux-mutation-product.log@4a28efacf8c8f7d8fd0c2850c18d366061c6de5fd1bbcd9c91bbe84d015bcf09`.
`C/linux-mutation-verification.json` records exact argv, actual CWDs, observed
exits, complete semantic comparison and provisioning. This closes actual-engine
verification of the repaired owner on Linux. It does not measure scores for the
large canonical target sets, and does not claim native macOS support. Only our
named container was stopped after retaining its evidence; no other container was
modified. With no running containers remaining, Docker Desktop was stopped to
restore its initial service state. Public-image bootstrap used a task-local empty
Docker credential configuration after the user-profile credential helper stalled;
no user credentials or Docker configuration were changed.

Both canary jobs now compose the existing pinned canonical runtime setup profile
(lint/test/runtime). A separate empty-cache environment imports the actual
`local_production_canary` module successfully without ML extras or borrowed site
packages. The four named orchestration tests exercise deterministic result,
failed scorecard and live-provider exclusion behavior; they control policy
execution. They do not establish a canonical-production workload's scorecard or
hosted CI success. Complete earlier commands/outputs are in
`docs/superpowers/journals/apparatus/station/2026-09-10-stage2.md@272d3bbc4cf7fcefe51a76ef78869064557eeaa9`.

The same four absolute canary nodes subsequently passed on the cold checkout from
ROOT and PRODUCT, 33.13 and 25.37 seconds respectively, no skips or traceback.
Full outputs differ only in elapsed time:
`C/cold-canary-root.log@d6d4f545698d830ea4e5c9203f38f2eba5951bdb2dc465fe4e2d923006f64cc6`
and
`C/cold-canary-product.log@13e3601696329a15acf56dd4c8d462648b96fa7c6f663b371b107a6a7032486e`.
`C/cold-canary-verification.json` names each actual node and its interpreter.

## Four fresh observations: same versus distinct

| Observation | Adjudication | Deciding evidence / route |
| --- | --- | --- |
| Detached freshness SIGABRT versus a working integration station | **Same two registered defects**, not one merged row: broken private interpreter and separate unavailable-measurement classification. | A1/A2 reproduce both mechanisms. Do not compare the preparation-failure count to a completed artifact-drift count. The final normal pair compares complete family/output identities; the offline pair compares complete UNRUN family/phase identities. |
| Plain `uv run pytest` lacks Hypothesis/pytest-benchmark | **New distinct default dependency-selection defect.** | Default dev group now composes existing `policy-engine[test]`. No package version changed across the complete 418-package lock census. Default fresh pytest executes the real ODS node twice without explicit extras; `C/cold-default-pytest-{root,product}.log`. Architect should register this separately under workspace/default-test provisioning. |
| Offline sync cannot obtain uncached JAX; another lane borrows site-packages with `.pth` | **New distinct package-availability defect**; the workaround additionally changes evidence provenance. | Empty-cache exact offline sync fails for locked jaxlib 0.8.2. Online frozen provisioning succeeds without borrowing. The particular older `.pth` path/bytes were not supplied, so that lane's reproduced provenance is `not_established`. Architect routes offline prerequisite declaration to DevX; original lane owns recapture of its results under a provisioned station. |
| Earlier dashboard “three failures, all jsonschema” | **Two same-defect instances and one distinct cause.** | Original `CI-S01` and `CI-S03` are wrong-Python jsonschema failures, covered by row 3. `CI-S02` is canonical Node executable-provenance mismatch in the fixture producer. The fixture now uses the actual authority's Node selector; tampered path/hash/version still fails. Do not close S02 with a dependency line. |

The default group change affects all lanes that use plain `uv sync`/`uv run`:
pytest and its repository-required plugins are now provisioned by default. Explicit
CI profiles retain their meaning. The six-line lock metadata change preserves all
418 package entries/version pairs (`C/dev-lock-version-census.json@7fedb7439aff340038bfd5957cc0b6c77aa52da0aff63b4aa19a93db6384b29c`).
`lefthook.yml` was not modified. Shared generated-client scripts use the existing
locked workspace binary; fresh lanes must install the lock before generation.

## Cold station and two-directory proof

`A/cold-initial-station.json@118640ee4c32c92744ab178067f660a183d81c9bac8c3296bb9e6a976acbc78b`
records absent `.venv`, root/app node_modules, UV/pnpm/Corepack/Playwright caches
before provisioning the new detached checkout. No production-data mount or
system site-packages forwarding was used. Node is 22.22.2, pnpm 10.33.2, uv 0.9.21
and Python 3.14.3. Corepack is explicitly pinned in outer-directory invocations
because its nearest-package lookup happens before pnpm's `--dir` handling.

Fresh frozen pnpm installation reports reused 0, downloaded 1,213, added 1,215.
The default Python invocation installed its locked environment from an empty
cache; a subsequent explicit sync added the existing lint/test/runtime/ml/mutation
extras before measurements requiring them. Chromium was downloaded into the
checkout's initially empty browser cache. The full-wave environment was not
mutated after freeze. Provision logs are `A/cold-pnpm-install.log`,
`C/cold-default-pytest-root.log`, `A/cold-complete-station-sync.log`, and
`B/cold-chromium-install.log`; actual origin checks are `B/cold-origin-probe.log`.

`ROOT` means `.worktrees/apparatus-cold`; `PRODUCT` means its `policy-engine/`.
Both calls in each pair use the same absolute measuring executable and arguments,
same tree and same declared environment. Runtime/log timestamps and initial
installation chatter are not compared as artifact findings. Tracebacks and
provisioning were inspected before verdict/identity comparisons.

| Check / exact measurement arguments | CWD pair / exits | Complete comparison |
| --- | --- | --- |
| Absolute cold `polisyos-tools architecture guardrails check` | ROOT / PRODUCT, 0 / 0 | Byte-identical full output; four exact families, eight exact outputs; no traceback. |
| Same command with `UV_OFFLINE=1` | ROOT / PRODUCT, 2 / 2 | Byte-identical full output; all four families UNRUN at environment phase for unavailable jaxlib; no artifact pass/mismatch and no traceback. Each measurement creates a fresh private cache. |
| Absolute cold `polisyos-tools diagnostics gen-schema --check` | ROOT / PRODUCT, 0 / 0 | Byte-identical full output; full scan, 101 models, no traceback. |
| Absolute pinned `uv run --frozen --project <PRODUCT> pytest <PRODUCT>/tests/repo_quality/test_dependency_runtime_witnesses.py::DependencyRuntimeTests::test_ckan_reads_real_ods_and_enforces_limits -q` | ROOT / PRODUCT, 0 / 0 | Same real ODS node passes; first call provisions the empty-cache default environment, second uses that exact lock/environment. No missing plugin or collection error. |
| `git hook run pre-push` | ROOT / PRODUCT, 0 / 0 | Actual installed hook selects typecheck only; same three tsc configurations, no traceback. Output differs only in elapsed seconds. |
| Full dashboard coverage and exact ratchet | ROOT / PRODUCT | Suite 0 / 0, ratchet 1 / 1, combined 1 / 1; complete test and coverage sets identical, same statements rejection. |
| Four named canary orchestration nodes | ROOT / PRODUCT | 0 / 0; complete selected four-node pass set identical, only timing differs. |
| Four real mutation nodes in fresh Linux container | `/` / `/repo` inside Linux | 0 / 0; complete persisted fixture outcomes identical: pass, fail, UNRUN, UNRUN; no skipped engine test. |

The first three pairs' full invocation/env/exit/source receipt is
`A/cold-station-verification.json@8452d3c7b386e80bf42a4e63512b721ee81a4b0c45301de051de62d47ab158db`.
Full guardrail output SHA256 is
`9fa49e2a57ea7578043fb7d62548f19b0e0f0734b1ace31d1943d46686829e18` for both normal
logs and `6de872d5b7d4b442eb95a37ad8254d8b8fa27a2a96789f0a99b4012fb0efbd75` for both
offline logs. Full schema output SHA256 is
`dbee374e5114ba5123961d030877a29259cda5a833b0a1577cc356b95fd08f05` for both logs.
Their wall time was not separately instrumented.

ODS logs have hashes
`a40d79e3d77dae5063448e85047affcd6ac7f4fd522703331d8210bf414913b1` (ROOT) and
`423b1d0e014eb1eab96f4420f7b344c2615be505dd574b756ac884826ca74f2d` (PRODUCT).
Hook logs have hashes
`7de04b5fb9c3d7adf248564125bed311b10d83e5b343e338e6b3387712626878` (ROOT) and
`5b6ec52f93d1c1257482052031f692fded54c909b68597454bdb9508a26a161d` (PRODUCT).
`C/cold-hook-verification.json` records actual installed hook/config hashes,
literal argv and environment, and measured 16.48/16.80-second runs.

ODF's complete canonical-source reconciliation and modified-wheel hash rejection
are C-ODF in the station decision. The canonical sdist hash is
`db766a6e59c5103212f3cc92ec8dd50a0f3a02790233ed0b52148b70d3c438ec`; the vendored
wheel/lock hash is
`1d1c3ea36a422d3c5cd4c2457ea0e0be59841d6c26d28bd3d5e43f060565d11b`.
The negative is a valid rebuilt ZIP/RECORD with changed `odf/__init__.py`, not a
malformed archive. `C/odf-hash-probe/sync-original.log` exits 0 and
`sync-modified.log` exits 1 for hash mismatch. Empty-cache offline failure is
`C/offline-empty-station.log@07538434cd68e13b2e979dbe74235057614432f1c5b19da72cb9aec414083922`.

## Incidental findings and named handoff destinations

| Finding | Disposition / destination |
| --- | --- |
| Current dashboard coverage adequacy | NEW completed artifact rejection, separate from unavailable execution. Frontend test/surface owners should address real unexercised code, including `GlobalShortcuts.tsx`, `ReproduceRunButton.tsx`, and mocked `useScenarioCapabilities.ts`. The first complete 281-file coverage map reports 7,047/8,277 statements (85.13%) against the unchanged 85.57% floor. Historical regression ownership is **not_established**; our tests/config intersect the measurement denominator. No arbitrary coverage cases or lower floor were introduced. Complete census/source-range inspection: `C/coverage-adequacy-analysis.log@09a1f8f39bffdddc7c1a4d2eb4767ba896f3a8cb614ae2d86bcefc8c1d665788`; reproducible harness `C/coverage_adequacy_probe.py@2e8873f63a90852c3f5e23640f58bd2d0420948814d5f0bab6ecee492e741081`. |
| Historical product/architecture/docs failures | Exact C-CI IDs retain owners and falsifiers: architecture import/exception/cycle/shim/size/directory contracts to team-architecture; CAS and registry injection to Runtime/Core; epoch fixture/status and OpenAPI examples to runtime epoch owner; incomplete metrics collaborators to Runtime tests; credentials mapping/scanner mismatch to Fabric/Core scanner owners; deep-copy substring gate to Scientist/calibration gate owner; publication-aware broken links to docs/brand publisher. They are not repaired by changing apparatus thresholds. |
| Historical cancelled/skipped jobs | CI workflow owners must obtain actual later hosted receipts for S10–S13, R16/R20 and F24/F25 subject to their event conditions. C02 live-provider exclusion remains intentional. No push was authorized, so no hosted aggregate closure is claimed. |
| `test_checkpoint_scope_uses_candidate_security_route` in `tests/repo_quality/tools/test_architecture_phase3.py` | Exact slice-base replay also fails: it queries deep-import violations expecting an approved Core security route, but receives no such violation. Our changed paths intersect its input denominator, so P41 disjoint ownership is **not_established**. Route to Scientist/architecture test owner. Do not call the whole file green or exclude this as proven inherited. Current/base full logs: `A/architecture-phase3-green-first.log@3f829be5db5b280af48025a2fa61843a3c1e75a788858c3e5a25c0dc4ace0dea`, `A/base-checkpoint-scope.log@f2a8d5245580c75cd88bcab2bf4d03e44943e2c4ee710a5a9828a9b14e1fa3bc`. |
| Package-gate docs census includes ignored raw Python scratch | Route to team-architecture's source-denominator owner. The exploratory current package report is not a pure committed-tree baseline; no inherited/disjoint claim follows. Its complete 248-item class distribution and source subjects are retained in `A/baseline-package-import-gates.log@4e1b4eefdfa276f1a7a575a0707e4e986976db3b4c58fb513fe89fe415a94a9f`. This is separate from the confidence owner's verified no-raw dependency set. |
| Capture implementation provenance binds five declared files, not transitive imports | Route to dashboard evidence provenance schema/producer/consumer owners. Actual helper-byte replacement leaves the existing five-file aggregate unchanged. The bounded residual is established in dashboard contribution B2; no claim of transitive closure, and no silent authority-schema expansion. |
| Optional all-generated producer protocol | Route to generated-artifact manifest/producer owner. Default required families are repaired; heterogeneous optional commands still lack a common completion protocol. Do not extend the closure claim to that mode. |
| Vendored wheel inclusion in built sdist | Route to packaging/distribution owner if sdist distribution is required. Checkout frozen install/consumer and integrity are proved; no new distribution contract was inferred. |
| Unsupported native mutation engine | Route to DevX/toolchain owner for a compatible engine/runtime/platform combination or upstream native fix. The current native station emits deterministic UNRUN; Linux witness is separate. Never count the four native skips as real mutation execution. |
| Borrowed `.pth` lane results | Route to original lane owner for recapture with its exact source/lock/interpreter; path and bytes were not provided, so historical result provenance remains `not_established`. |

## Verification bounds and final audit

No directory-wide pytest, backend verification or CI-parity run was used. The
full dashboard suite is the user's explicit exception. Deciding gates were sole
commands with output redirected; tool-observed statuses were retained separately.
No `gate; echo $?` result was accepted. Failed initial harnesses and interrupted
overlapping-environment runs remain raw non-receipts; their later frozen replays,
not filenames containing “green”, decide the result.

Targeted Ruff, changed workflow policy, declared test-target validator and
actionlint passed. Actionlint names exactly `.github/workflows/abi.yml`,
`.github/workflows/core-runtime-release-gate.yml`, and
`.github/workflows/policyos-canary-matrix.yml`. The declared-target validator
walked its complete 23 CI declaration files/116 unique pytest references with no
missing target. Source changes were reviewed before the expensive frozen wave.
Dashboard lint/typecheck and individual red/green records are in its contribution;
mutation admission/dispatch and canary records are in the station contribution.

The failure/repair register was reopened before closeout. Relevant pattern pass:
P29/P31/P32 replace declared execution with actual producer/consumer witnesses;
P35/P36 use complete populations and finding IDs; P37/P38 separate environment
availability from artifact evidence; P40 widens shared computation boundaries and
declares the native/provenance residuals; P41 keeps unknown red ownership explicit.
No new policy authority or product closure capability is claimed. Apparatus
surfaces are CLI/test outcomes, generated comparisons and persisted mutation
receipts; new product API/dashboard surfaces are `surface_out_of_scope`.

Independent review found no missing original row or unsupported inherited-red
claim in this completion journal. The final wave used source
`272d3bbc4cf7fcefe51a76ef78869064557eeaa9`; the detached cold tree remained clean.
Only this completion journal is added after that freeze. Final attached-branch
readback is performed after the journal commit and retained locally as
`A/final-branch-readback.log`; the delivery SHA is the attached branch's journal
commit, while the measured source SHA remains the explicit freeze above.
The architect receives the finding routes here and in C-CI; no debt-register or
ledger mutation is part of this delivery.
