# Q2 installed-runner preflight review

## Assessment

**Partial preflight; no installed-wave pass is established.** The reviewed runner has a plausible source-to-wheel-to-installed-consumer design and its selector/fixture binding and output-retention behavior passed the independent checks below. The three build/install profiles, cold installed imports, and 100-test consumer set have not run on the required Linux worker. This is an independent code assessment only; it makes no G-acceptance or formal-closure determination.

P40 classification up front: the earlier output-loss escape is a **NEW class** from the selector-to-fixture binding escape. The current runner closes the output-loss escape with `pytest -s`, streaming stdout/stderr to retained files, and receipt hashes; the reviewer’s successful and timeout probes exercised that behavior. No second output-retention escape was found in this check. The actual consumer invocation does not set a timeout, so timeout behavior is only verified at the helper boundary.

## Frozen review denominator

Product source was read from the assigned candidate checkout, not the primary checkout:

- Product `HEAD`: `68b8ac5c32e03309ad888cb3799ad1c574fbdca7`; tree `7966c18c0557e8f43fd09e03f3c4eda9f987e458`.
- The selected ten source, fixture, and baseline-JUnit inputs in the static report match that commit byte-for-byte. The working tree has declared peer changes; the runner correctly requires a later clean tracked tree and an exact committed SHA/tree before it starts.
- External Q2 inputs reviewed: `raw/run.py` SHA-256 `5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932`; `installed-wave-manifest.json` `ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7`; `installed-wave-recipe.md` `e496a95d395d860747ba8a457630551040c32a8442be1de12af975fd4d86410e`.

These hashes are the reviewed input denominator, not evidence that an installed wave executed. The runner records its own and the manifest’s hashes in the run receipt but does not accept expected runner/manifest hashes as an invocation guard. Before the Linux run, the operator must compare the live external-file hashes to the reviewed values and retain the resulting run receipt; the runner is ignored external machinery, not part of the product source archive.

## Property-to-evidence review

The source-driven AST preflight resolves the selected tests and their local helper calls, then binds dynamic worker fixture kinds to concrete fixture files and callback functions. In the reviewed source it resolves `dowhy` to `test_dowhy_worker.py` helpers `dgp` and `admit`, and `gcm` to `test_gcm_backend_contract.py::test_actual_gcm_job_persisted_fresh_reader_and_scientist_consumer`. Callback existence and call arity are checked before any build. This is a substantive selector-to-fixture check, not a presence-of-name check. Its current static result is 91 pinned Q2 IDs plus nine declared selectors, or 100 selected IDs; **the count is only a planned denominator until actual collection/JUnit equality is observed**.

The recipe’s consumer command uses the isolated installed interpreter (`-I`), pytest `--import-mode=importlib`, and `--confcutdir <frozen-product>/tests/unit`. Static census found 32 product conftests; the root `tests/conftest.py` path insertion at lines 24–31 is excluded by that cutoff, while the selected nested unit conftests are retained and none injects a source path. The pytest plugin records loaded `polisyos`/`tools` origins and checks them against installed `purelib`, and checks the frozen/live product roots are absent from `sys.path`. These are appropriate runtime discriminators, but their result is still **UNRUN** until the Linux consumer executes.

The runner specifies three real artifact paths: source wheel, wheel rebuilt from the source distribution, and wheel rebuilt from the GCP package archive. Before the builds it reconciles the complete `hatch.toml` force-include mapping with the 11-row manifest; it then checks asset bytes through source, archive, wheel, and installed locations. It also checks the GCP-selected sibling sets and the digest-domain registry through the installed default path. Static mapping/byte checks passed for the reviewed committed source; no archive, wheel, package install, registry call, or installed import was executed here.

The consumer-output property is independently tested. The runner’s actual pytest arguments include `-s`; `run_command(stream_output=True)` writes process stdout and stderr to separate files, and the consumer receipt requires both and records paths, byte counts, and hashes. A reviewer-created one-test pytest probe emitted distinct stdout and stderr markers and returned 0; both markers were present in the separate files. A second probe used the exact runner helper with a 0.2-second timeout: the child timed out, `timed_out=true` was recorded, and already-written stdout and stderr markers remained in their respective files. Raw receipts:

- `LOCAL/q2-packaging/raw/reviewer-capture-probe-20261009/capture-probe-receipt.json` SHA-256 `37117e0404deb4396d9deff16f948a29163400c7bb7a29cc1962a9ae9106306b`.
- `LOCAL/q2-packaging/raw/reviewer-timeout-probe-20261009/timeout-probe-receipt.json` SHA-256 `2e33ca76b9b7689b6c05b939f56e161795b1f50b970f8f49f356880f35048156`.

The six selected dependency-profile tests include a selector named `test_missing_unreadable_or_corrupt_digest_registry_returns_source_not_established`; source inspection confirms its body tests malformed TOML only. It does not exercise missing or unreadable registry paths, so those two cases remain outside this selected regression set. Do not cite this selector as evidence for those cases.

## Operational and quality limits

The required target is Linux with a prepared Python 3.14 app/test environment and a Python 3.12 DoWhy 0.14 worker (or the runner’s locked provisioning path). The consumer timeout is deliberately unset in the recipe until its wall time is measured; set it after a measured Linux run if a bound is required. The recipe’s approximately 1.5 GiB scratch estimate came from a prior source snapshot and excludes GCP archive/platform overhead and creation of a worker environment. Measure capacity on the actual Linux target before starting the single heavy wave.

I audited process construction separately from Ruff’s subprocess warnings: commands are argument arrays passed to `subprocess.run`/`Popen`, without `shell=True`; the shell invocation is a fixed `bash` call on the frozen `ops/cloud/gcp/package_repo.sh` path, with values carried through environment variables. Repo paths and Python paths are passed as argv, and the source SHA/tree are checked as full hex values against actual HEAD/tree. No command-string interpolation of user-provided arguments was found. This is a bounded static input audit, not an execution sandbox claim.

Ruff was run from the candidate product venv against the exact external runner; it exits 1 with **83** findings in the final captured output (the earlier author summary of 81 is stale). Findings include import/style, annotations, line lengths, assertions, subprocess rules, and XML parsing rules. This raw runner is ignored external orchestration code, so the Ruff result is recorded as tooling/style debt rather than misreported as a product test failure. It does not establish a pass for the runner’s unexecuted artifact chain.

## Reproducible review evidence

- Static preflight output: `LOCAL/q2-packaging/raw/review-preflight-static-final.json`, SHA-256 `12760633c2fccf38481c6d5d88b89394a04417cf547a537ea0d2e72dd87f3c8d`. It records exact source and external hashes, selected-input equality, 11 asset rows, source-sdist inclusion, 91-case baseline JUnit with zero skip/fail/error, conftest census, selector/fixture bindings, AST parse, pytest flags, and the capture contract.
- Ruff output: `LOCAL/q2-packaging/raw/review-ruff-final.json`, SHA-256 `e3170397954a1c7adb6e4a88fbc6c46014d72da599c5c78d099798333014c8f7`; command was the candidate `.venv/bin/python -m ruff check --no-cache --output-format concise <raw/run.py>` and exit status was 1.
- No Linux build, wheel, sdist, GCP archive, install, DoWhy provisioning, selected 100-case suite, or heavy/native test was run in this review.

## Remaining discriminator

After source freeze, run the exact external-input hashes above on the prepared Linux worker and retain the complete output. Acceptance of the installed-consumer property depends on the actual three-profile run proving all 11 installed asset bytes, fresh installed-reader behavior, module origins under installed `purelib`, no source-root leakage, exact 100-ID collection-to-JUnit equality, and zero skips/failures/errors. A static plan, author-reported helper probes, or the successful synthetic capture probe cannot substitute for that execution.
