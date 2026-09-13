# Correspondence vocabularies evidence

Commands ran in this lane’s `policy-engine/` unless noted. Stage 1 was committed
as `9ccb4c14864269666d6dc2abae18081696b6f2e4` before production edits. The bounded
Stage 2 mechanism was committed as `de93777791f64c452b157f6ac9ba183dffee05dd`.
Every delivered path was reread using `git show <commit>:<path>` and compared
with the attached `codex/correspondence-vocabularies` worktree.
Raw evidence is local and gitignored; absence at another checkout is a non-receipt, not a passing result.

## Commands and process results

| Command / operation | Own exit | Result |
| --- | --- | --- |
| Worktree doctor create and resume preflights from integration checkout, exact requested branch/path | 0 / 0 | Admitted before lane creation; complete JSON and stderr retained. |
| `corepack pnpm install --frozen-lockfile` | 0 | Workspace dependencies linked, 44.7 seconds. |
| `python3 docs/research/policy-operations/correspondence-vocabularies/source_census.py --repo ..` | 0 | Complete current tracked Python census; exact invocation arguments are recorded in JSON. |
| Historical census with same script and debt-nature-survey worktree repo | 0 | Complete historical tracked Python census; source equality to historical census base separately checked. |
| Independent case-insensitive `git grep -l -i -z` at both pinned commits, each estimand/normative literal | 0 each | Complete path sets reconcile to Python reader; predicate and commands in source-census report. |
| `python3 -m unittest discover -s tests/repo_quality/tools -p test_vocabulary_source_census.py -v` | 0 | 6 behavioral tests, 7.532 seconds, final output. Initial invalid-UTF8 Git-diff failure retained and fixed. |
| Same suite with casefold removed, then with unreadable-member completion condition removed | 1 each | Each removal leaves markers but causes 2 assertion failures. |
| Shared root `.venv/bin/python -m ruff check` on research script and mirrored test | 0 | Bounded lint; complete output retained. |
| `env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/fabric/test_non_data_acquisition.py tests/unit/fabric/test_ceiling_relations.py tests/unit/foundry/validation/test_legal_correspondence.py tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py -o addopts= -q` | 0 | 140 passed, 6 warnings, 449.90 seconds. Source resolves from this lane; environment is shared, not a provisioned lane venv. |
| Independent integrated R1/R2 reviews | review findings | DS15 negative projection is independent; commissioned consent scope retained; stale lane destinations corrected. |

No production-source changes precede the Stage 1 commit. The table above is the
Stage 1 checkpoint; Stage 2 receipts are distinguished below.

## Raw receipt references

This table identifies the Stage 1 raw receipts listed here. Per-scenario probe
directories are retained beside their deciding suite outputs; no derived data
copies are committed.

| Raw path (relative to this journal) | SHA-256 |
| --- | --- |
| `raw/acquisition-commission.json` | `0a95afd58a66c4c4ddf408c2c05771ee8abb403f064730023baf7a00b3cbcb09` |
| `raw/admission-create.json` | `73bf681ae5e419d86f16f3405af258d56dcc6000aa14d13673d0466c1f026a32` |
| `raw/admission-create.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/admission-resume.json` | `67ce73a6dc41656ae5a699515802a3a7212179c1b1598396f1f4dab7fb6c2c74` |
| `raw/admission-resume.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/case-removal-tests.txt` | `492ffed11502b4cdd843a6dd7badf436dfecc5c68d816ad339ef8e1f51e5a845` |
| `raw/census-reconciliation.json` | `1050ffc03931ea9fc5b914981b5005f87a4ff0acb15b85beccef73035b3dc091` |
| `raw/census-tests-final.txt` | `d76484ad4211f4bb895929797f4796b471717efd5d11cdb034550c31ad29f7ba` |
| `raw/census-tests-fixed.txt` | `d7af2d84dc6b921f03560c342047f63a23d0a7d80d8a073dd209a51fc78d367a` |
| `raw/census-tests.txt` | `090b1bd9088dc5c15812b6fd6761865df30337568cfebf104d4c213e2b999a92` |
| `raw/existing-owner-tests.txt` | `8526b30570dbc7da91229fce3bc0fa5f3818afb1239bf2706c042a4e25941f3e` |
| `raw/git-estimand-current.bin` | `10896796fb2b07df37d56b92f87677a29bd3f01bc241d67c4834549161838007` |
| `raw/git-estimand-historical.bin` | `0f0cb13db9a2f2e496a2d3aa224f2e817ef334388ad1da3016cd68ad3ca4ddcf` |
| `raw/git-normative-current.bin` | `847862ddb707a59157d9e24fd2caf6d2be027ac1a535d361729a0794b48307ad` |
| `raw/git-normative-historical.bin` | `b25ed127e0b7addfe6f0167e11b85fc54c47dec8664bd924dcdc01e81a6ee4e2` |
| `raw/historical-source-census.json` | `b194ae95a9c2999a264cdffb9118174207ce474727b99ce52a24f2a35ab47b9c` |
| `raw/historical-source-census.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/historical-source-delta.txt` | `8106f19a36c0e828b169f1d3c6402123878a0c0497d54ec35bea363a2cb194a3` |
| `raw/local-links-before-evidence.json` | `ef637b9175771a8fac1e4062a624e44d42ad8d1c85d9bcf844d6575273f6b0e1` |
| `raw/pnpm-install.txt` | `53d579ccc49052df960c089fb95cca392b89249e44b4fb321d27fa5844f9b3f7` |
| `raw/r1/integrated-review.md` | `d95c5452f683f3ceb96b3643b7182e5173dcec001d8cefc01478101ec0f1d3a6` |
| `raw/r2/integrated-review.md` | `205d089158823c4802e8d8cb046a7bbe5c7db8e88e0c8f34672ad3e2e60ac9cf` |
| `raw/r3-r4/row-denominator.json` | `518bb3a8bf5b512048bbef4c6c1e9458bffd6559599713cee5a4e3dc74b633a9` |
| `raw/ruff.txt` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `raw/source-census.json` | `4df0ca42247becbb557b4c725be09e2759cf895dc0f75f5d7cf425b05978f4f5` |
| `raw/source-census.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/unreadable-removal-tests.txt` | `ad9c9f11a4ae3041da33e4c94f30ede0f0b5ac9321f999583e9133919924ff21` |

## Stage 2 scope and final-source checks

The production source freeze is `de93777791f64c452b157f6ac9ba183dffee05dd`.
The final import/hash delta was independently reviewed before the final checks.
The four mechanism paths are enumerated in the Stage 2 plan; no new public DTO,
OpenAPI snapshot, register, ledger, façade or guardrail baseline was written.
Python commands use the integration checkout's interpreter with this lane's
`PYTHONPATH=src:tests:.`; this is not an isolation-local dependency receipt.

| Exact bounded command / operation | Own exit | Result and limit |
| --- | --- | --- |
| `env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/runtime/quality/test_non_data_acquisition.py tests/unit/runtime/http/test_non_data_acquisition_projection.py -o addopts= -q` | 0 | 31 passed, 16.46 seconds reported by pytest, on the final source. Service tests isolate the legacy lifecycle-manifest derivation and outer child carrier; canonical CLI, planner, CAS, source admission and worker payload recomputation are real. This is not the unmocked child-process proof. |
| `corepack pnpm --dir apps/runtime-dashboard exec vitest run src/features/runs/components/AcquisitionRouteDetail.test.tsx` | 0 | The selected file's 4 tests passed, 2.06 seconds. Existing fields render the candidate type, refusal and blocked action; renderer implementation unchanged. |
| Final bounded `ruff check` on the changed Python source/tests | 0 | Complete final output retained. |
| `raw/r1/stage2-import-boundary.py` through the actual guardrail helper | 0 | All four mechanism `.py` files, compared with the slice base, Stage 1 and the recorded baseline: no added deep-import edges. 1.001 seconds. This bounded result does not replace the full guardrail command. |
| Final canonical-verifier removal process probe | 1 (expected) | 460.871 seconds, no timeout. The unchanged forged-content test fails with `DID NOT RAISE`: removing owner recomputation while retaining receipt shape permits fabricated refusal reasons. |
| Final producer-CALL removal process probe | 1 (expected) | 448.474 seconds, no timeout. `F..`: the persisted readback fails on the nonexistent zero-digest receipt; both original foreign claim/gap negatives still pass. The callable and receipt-shaped output remain. |
| Ordinary operator CLI on the final source, command below | 0 | Persisted receipt `sha256:9c9873adc71f4400a4f8cd44691ac0bf61db643b9cdff8a9ef455217b97cb879`; its actual service/child consumption is a separate receipt. |

The operator invocation is:

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m polisyos.runtime.quality.non_data_acquisition --governed-root docs/superpowers/journals/correspondence/vocabularies/raw/production-demo --request docs/superpowers/journals/correspondence/vocabularies/raw/production-demo-request.json --gap docs/superpowers/journals/correspondence/vocabularies/raw/production-demo-gap.json --route-id education --run-id correspondence-vocabularies:operator-demo --at 2026-09-13T00:00:00+00:00
```

Its inputs deliberately declare an empty candidate demand, with claim/gap copied
exactly from the existing education route. No target, legal meaning, authorization
or institutional evidence is inferred. The dedicated artifact snapshot copies the
complete declared N13b families, their registry and the N13a source inputs; exact
input paths and hashes are retained in `raw/production-demo-inputs.json`. Runtime
publication does not write into the checked repository artifact tree. That tree's
actual lifecycle auditor includes new files regardless of Git ignore status;
repo-root publication would require the separately named AQ1/lifecycle registration
work, outside this lane's explicit no-register-edit scope.

The actual replay harness calls the ordinary service and only records the actual
child `subprocess.run` request/result; it does not substitute a validation result
or increase a production timeout. The outer service verdict, complete child output
and persisted packet must agree before this account claims a verified surface.

Earlier incomplete attempts remain evidence, not exclusions: the old acquisition
regression invocation ended with own exit 2 after 18 passes and two failures
(one child validation failure and one 120-second harness timeout); the obsolete
static invocation was retired with exit 143, and the interrupted guardrails command
ended with exit 1 and a CLI `UnboundLocalError`. None supplies a final green or an
inherited-red attribution. The initial production replay timeout and the later
successful pre-import-fix replay are retained separately; neither is substituted
for execution on the final hash rule. Incidental destinations are CV-S2-TEST and
CV-S2-CLI in the implementation account.


## Executed final chain and diagnostic dispositions

The final unmocked replay command was:

```sh
env PYTHONPATH=src:tests:. CV_WORKER_IMPORT_PROFILE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/correspondence/vocabularies/raw/production-demo-read.py
```

Own exit **0**. The real child process returned **0 / passed** in **46.3369
seconds**, with its ordinary **184-second** timeout unchanged. Import profiling
only adds Python's import-time stderr observations; it does not substitute owner
results or increase a timeout. The persisted packet is `available`, carries
`candidate_non_data:not_established`, `shape_not_established`, reason
`not_established`, gap class `not_established`, and action `blocked` for the exact
education route. Its artifact identity is
`sha256:517736a6e63afc39ec4aeb2b1b223350655d3a4d8eb86115c75985d8c41e20e2`;
its projection identity is
`sha256:43926a7f43a86e5115169a5f078a792211b44f701f6ee8dd8903ccd8b2dabb3e`.
The prior final-source timeout remains under `raw/final-timeout/`; no inherited
attribution or causal performance diagnosis is inferred from this successful retry.

The unchanged acquisition worker tests were rerun serially through a recorder
which calls the real `subprocess.run` and returns its actual result:

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/correspondence/vocabularies/raw/retry-worker-tests.py
```

The harness invokes exactly
`pytest.main(["tests/unit/runtime/http/test_governed_projection_validation_worker.py", "-k", "acquisition", "-o", "addopts=", "-x", "-q"])`.
Own exit **0**, **10 passed / 15 deselected**, **292.58 seconds** reported by
pytest. Its existing per-child 120-second timeout is unchanged. This includes the
previously failing registered-validator and marker-preserving payload-drift cases.
Each real worker request, stdout, stderr and process result is retained under
`raw/worker-retry/`. The earlier failures were not excluded as inherited.

The exact final lint scope is the four mechanism paths in the plan, the two new
unit-test paths above, the research census script and its mirrored repository-quality
test. `python -m ruff check` on those explicitly named paths returns **0**;
`raw/ruff-final-complete-scope.txt` is the final output.

The required invocation diagnostic ran once over its complete built-in selector:

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m polisyos.runtime.quality.production_invocation --repo-root . --base 28b8a1a420e746b54fbd0b87f73fad1fc4821ba5 --receipt docs/superpowers/journals/correspondence/vocabularies/raw/production-invocation-final.json
```

Own exit **3**, `UNRESOLVED`, `coverage=partial`, `regressions=[]`.
The receipt's selector is all Git-tracked `src/**/*.py`, `tools/**/*.py`, and
`tests/**/*.py` at the pinned base and current source; entry roots also come from
`pyproject.toml` project scripts and non-test `__main__` guards. No path subset was
substituted. Its new unresolved mechanism is
`polisyos.runtime.quality.non_data_acquisition._ProjectionCAS.get_bytes`.
The retained disposition identifies AQ1 `_resolve` and the planner-report loader
as actual callers, with executed read/traceback evidence. The static instrument's
receiver/super dispatch limit remains `unresolved_by_construction`; its
`runtime_invocation_established=false` is preserved. It does not displace the
independent actual execution above or declare an absent producer. Its large raw
receipt is gitignored, not embedded into this journal.

The standalone ledger invocation, with no other command in its shell invocation,
was:

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python tools/quality/validation/check_debt_ledger.py --check
```

Own exit **0**. Its declared coverage is explicit file-reader operations, with
unmeasured imports/Git/subprocess reads, source-standing and owner-appointment
semantics. It retains informational unknown-host closure selections because the
collector's `uv.lock` differs, an unsupported Vitest selection, shifted status
columns and standing supplied from ambiguous/prose sources. Exit 0 is not a
receipt that those closures were exercised. Destinations are CV-S2-LEDGER.

A frozen offline lane-environment attempt used
`uv sync --offline --frozen --extra runtime --extra ml --extra lint`, own exit **1**:
the locked `jaxlib==0.8.2` wheel was absent from the cache. The incomplete `.venv`
was moved to ignored `raw/failed-lane-venv/`; it is never used as a working lane
environment. The shared interpreter limitation remains explicit (CV-S2-ENV).

The first completed standalone guardrail invocation was:

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m tools.cli architecture guardrails check
```

Own exit **1**, retained in `raw/guardrails-check-final.txt`. This lane edited
`stage2-results.md` during its generated-output probe; that worktree-change
finding is ours, not inherited. It also reported runtime OpenAPI snapshot and
trust-claim-posture generated-output drift, while the API-client and dashboard
API-type freshness checks passed. Their provenance remains `not_established`;
the named destinations and snapshot restriction are CV-S2-GUARD. Every tracked
file is frozen throughout the concluding repeat. The repeat result is appended
after that command returns; no unrun final green is asserted here.


## Stage 2 raw references

The named receipts below are read in full and hashed. The worker-repeat subset
is every immediate regular `.json` or `.txt` file in exactly `raw/worker-retry/`;
those are actual child requests, responses and process observations, not a derived
source inventory. Unreadable or symlinked members abort this reference pass.
The other paths are individually named deciding outputs, inputs, probes and
bounded review accounts. No complete-set claim is made about all scratch files.

| Raw path (relative to this journal) | SHA-256 |
| --- | --- |
| `raw/before-import-fix/production-demo-read.txt` | `ed746c05a74abb7d2e185b39c18f96dac6d4be729bd32719c2793231c99b7f81` |
| `raw/before-import-fix/stage2-final-tests.txt` | `36a92710e12127ffa6f7e240153ea1f15a56c5a6094a363829448e25bad01d46` |
| `raw/existing-acquisition-projection-tests.txt` | `e953fa948c56c95133620bfab6e4dcfa429ce26251a07e4be423f49c7a58af24` |
| `raw/final-timeout/production-demo-read.py` | `d17caf9c51a0b2998f9d199eca9e85fb43f7d09092adea152042671c48f18d85` |
| `raw/final-timeout/production-demo-read.txt` | `5bb25a66a158350b25ab83a6c80adc70269c84276ee888278dae4a7719424fb2` |
| `raw/guardrails-check-final.txt` | `a602ee40b74a04525c5dd151e56b4e5d9e2dae58ca6d188df345911280bc14e9` |
| `raw/guardrails-check.txt` | `051b2b624c8d2e96b2395769c40e4076155ab6e917ed3cd133cab06780cc26a4` |
| `raw/lane-environment-sync.txt` | `1a8d8ac37e7d78a1f4ce2890ada52e0381641c548c01153a7d245857878b6db8` |
| `raw/ledger-check-final.txt` | `dd18cca543ff7e0f55025666ef7f2c9e6cd9fb799063bce1b851ffa1c2174441` |
| `raw/ledger-check.txt` | `dd18cca543ff7e0f55025666ef7f2c9e6cd9fb799063bce1b851ffa1c2174441` |
| `raw/mechanism-branch-readback.json` | `f2a4c55e9dab33f09d3a6b596c9d809e2a4c8c0051877d911002d0207a2de442` |
| `raw/production-demo-cli.txt` | `2ba264d41a2c3fb2e09e140fcdd17ef509565d1b32b72dbb8ab3ce5723a81bbe` |
| `raw/production-demo-gap.json` | `6d2c20ee9bebc7e3ed3e15f49fefa575de87302c89bf171ff8073b7147cc8366` |
| `raw/production-demo-inputs.json` | `b198b1b5a6f6e12d00fd080d2aa2779ba07638207c72743860ca81ff035d5092` |
| `raw/production-demo-packet.json` | `894a2e78e6a2ff77ebd09fdfb23999659f5127c67778c8c4db19880e6ff534ab` |
| `raw/production-demo-read-initial.txt` | `5bb25a66a158350b25ab83a6c80adc70269c84276ee888278dae4a7719424fb2` |
| `raw/production-demo-read.py` | `9ffac203e373684e83e71263ec0d8c7dc198a7fbb91d3a47c53fe6f1c9a3c51d` |
| `raw/production-demo-read.txt` | `666d6d25270a6713b78bee2bd961a4be825c2cec45684a218a21cecfe91984dd` |
| `raw/production-demo-request.json` | `86559a570d091f0158dbe57f4321a6a00fd82c8993580b4a98f3556854b09103` |
| `raw/production-demo-worker-process.json` | `c270757eaaece78ee58ae55c75dc309fb812c26f9c66862c42ac21d2a7c66bfb` |
| `raw/production-demo-worker-request.json` | `d2fc283b5787871075c0b6cd4edde8572590804bc2fe91a3b2994f8f65ca7dfa` |
| `raw/production-demo-worker-stderr.txt` | `0a56636e4c488ac9ec81089a1bb6d530a773a906297944dfd5c953bda5904cd2` |
| `raw/production-demo-worker-stdout.json` | `d3d8f7504faddc2d253e4e97a7697ac4b41dfd79820066b8cf45479304be7160` |
| `raw/production-demo/architecture/policy_design_case/gy_aq1_non_data_projection/receipt-bundle.json` | `6b68deb21ffeef15f884b7a90bd5c785d39335babbbc7d62fe38997e933b798e` |
| `raw/production-invocation-final-output.txt` | `6195fe0eb4d5b86ad5b6af2ec13e56b4cc729803ee170c0ed87b8095f61f57cc` |
| `raw/production-invocation-final.json` | `d08a4dfc37532d5139926b6ea7c6e809124a36cc2fa93c48062a53931129b5b5` |
| `raw/r1/stage2-import-boundary-process.json` | `33e4057f7aa725bad2e29ef65c9429410cf25c40511fbb3bd2b598278fa67f88` |
| `raw/r1/stage2-import-boundary.py` | `0bcca8911ad81f7952c41cce585d1a12ea34583c86be759ea0d450cdd56382e7` |
| `raw/r1/stage2-import-boundary.txt` | `d296c85d1787519e7c4739c82365b7dd2b54f0c9b67f8d6f0f20bc473ecc0970` |
| `raw/r1/stage2-timeout-diagnosis.md` | `3fab6d2ce2c96a288836ef0e037b2eafc9dd7106b94ca21912cbc9aba207e195` |
| `raw/r2/stage2-acquisition-route-detail-vitest.txt` | `7ecb1891197bf025ff6807d4fac83a677a07c5d9041757f03e33317f81822103` |
| `raw/r2/stage2-import-hash-delta-review.md` | `be0a9bef97012f36d6c76bd2dbd9b4e68ae42db86cb186e60b60f67be249216d` |
| `raw/r2/stage2-source-review-rv03-delta.md` | `ad9ddd35847b11c5b0289d567d5bebac5c0a3bc3967439e37fd68bc430cf5868` |
| `raw/r2/stage2-source-review.md` | `6e29e286aea2ecb4c7c24612a30005376f029e809598b55eadac373551190e3d` |
| `raw/r3-r4/remove_producer_call_probe.py` | `a10ff3f33244225fe5b0529d18b8e2cb27816acf47189724a1fe7a4d3ee16f51` |
| `raw/r3-r4/remove_receipt_verification_probe.py` | `ed42278b418b15afdb40581ba715a8cd8135aa42d03004e3168273bda095ffcb` |
| `raw/r3-r4/stage2-call-removal-probe-final.json` | `9fa9b83b7f6162e1ce38e28c2839a21e79606d4b61236f384eb30299df2e93b8` |
| `raw/r3-r4/stage2-call-removal-probe-final.txt` | `dea87c6328fc0319b8ba16321b49a61284d580d2e4e2f95ae947b460c7659f7d` |
| `raw/r3-r4/stage2-removal-probe-final.json` | `19b7add3bbc64da2a7f8b18480006a03457d555b59674272ab7673f0f4a0ceeb` |
| `raw/r3-r4/stage2-removal-probe-final.txt` | `744f61f4effed763f8d9b8a5107738b9136bb89790e07cc574a476b3e443c372` |
| `raw/r3-r4/static-get-bytes-disposition.md` | `bbec977e73fcc0604a5b1324ca6d020aaf324b50468209cbc3972b2fb9537c5d` |
| `raw/retry-worker-tests.py` | `9a9a313df415220f3508e3c38dc7325a90a06654c18bcc6414f9a1fae0b8a25c` |
| `raw/ruff-final-complete-scope.txt` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `raw/stage2-final-tests.txt` | `19e4976705bf8ea413c0a9f48509d5bbf1f0402ec093643fd09e56dedc64a995` |
| `raw/stage2-invocation-output.txt` | `85aa35b3ba60126543b1088eb8029d430847685b05e038a8aed6706e128ff829` |
| `raw/stage2-ruff-final.txt` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `raw/worker-retry-final.txt` | `0f0e8daaff48c7d6db1a8b47337a0742928e1cb838aeb1b4df05212df5799253` |
| `raw/worker-retry/1.process.json` | `0c2bb4750a4abee44964b14e71b61ed5712f2cdedc925e75ed8f728324292634` |
| `raw/worker-retry/1.request.json` | `48f049655773dd0230ca7d70e93d90296694ea05418b28040c23e19a1ac2c1ea` |
| `raw/worker-retry/1.stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/worker-retry/1.stdout.json` | `f759fbf7dec49a44fdc8874c3081679baf34e4e82f7f797d611c11802e81ceff` |
| `raw/worker-retry/2.process.json` | `0c2bb4750a4abee44964b14e71b61ed5712f2cdedc925e75ed8f728324292634` |
| `raw/worker-retry/2.request.json` | `48f049655773dd0230ca7d70e93d90296694ea05418b28040c23e19a1ac2c1ea` |
| `raw/worker-retry/2.stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/worker-retry/2.stdout.json` | `f759fbf7dec49a44fdc8874c3081679baf34e4e82f7f797d611c11802e81ceff` |
| `raw/worker-retry/3.process.json` | `0c2bb4750a4abee44964b14e71b61ed5712f2cdedc925e75ed8f728324292634` |
| `raw/worker-retry/3.request.json` | `8129fc201a6d0e9c413580edb9232bd4b29b4a47112a256f9eacc4984071bca9` |
| `raw/worker-retry/3.stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/worker-retry/3.stdout.json` | `ed222305f0f8956d88104578703985e70ff705ff97ab6f95a5fb5814b8b16ccc` |
| `raw/worker-retry/4.process.json` | `0c2bb4750a4abee44964b14e71b61ed5712f2cdedc925e75ed8f728324292634` |
| `raw/worker-retry/4.request.json` | `03d17bda7e5c1a88f1f80609640a824eafd392466f03f7564475298d50cfc43b` |
| `raw/worker-retry/4.stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/worker-retry/4.stdout.json` | `1ef021a192b2ee57f9969308a22d794df3bfb1a3ac688fb7c44ed8f094eaa9d7` |
| `raw/worker-retry/5.process.json` | `0c2bb4750a4abee44964b14e71b61ed5712f2cdedc925e75ed8f728324292634` |
| `raw/worker-retry/5.request.json` | `fffef9d5f10311338ece59247cef2fc6d5df50b9a86b5ed41fc7b157780e45c3` |
| `raw/worker-retry/5.stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/worker-retry/5.stdout.json` | `199f3e8df066e06b46299ef0ad720959e34862f181c20030dbc04b82620b177d` |
| `raw/worker-retry/6.process.json` | `0c2bb4750a4abee44964b14e71b61ed5712f2cdedc925e75ed8f728324292634` |
| `raw/worker-retry/6.request.json` | `7b51ef39dfa61ca2674947caa038c10b2ef674a45a7f583d9885b1b34a814fad` |
| `raw/worker-retry/6.stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/worker-retry/6.stdout.json` | `0064dd039a442c6101028c7dfc908a603f0fe09e0b59c96a86517123d88a9f3a` |
