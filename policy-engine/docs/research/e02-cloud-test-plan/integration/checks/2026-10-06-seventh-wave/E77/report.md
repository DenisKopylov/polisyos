# E77 independent DoE selector receipt

**Result: PASS, 77/77.** The only executed selector was `tests/unit/scientist/methods/doe/test_plan_runtime_admission.py` from immutable candidate `70c4a14fc872f5ef66437d958ba63884ecdda168`, tree `3e654b07a3228d1b3d2d0bb2a3a91ae792068090`. Pytest reported 77 passed in 2.02 s; the complete child-process wall time was 3.635 s, exit status 0, under the explicit 180 s timeout. JUnit has 77 cases, no failures/errors/skips. Captured stdout is `stdout.txt` (249 bytes); `stderr.txt` is empty. The exact command, pytest args, environment overrides, output locations, and timeout are in `test-command.json`.

## Candidate inputs and provenance

The integration checkout stayed on `codex/e02-integration` at `127dc7ab8365d29eb656fe32c0c894f6cc971286`. Candidate sources were read with `git archive`; no branch/ref/checkout changes were made. The archived closure contains the candidate's complete `policy-engine/src`, the exact selector, existing test `conftest.py` ancestors/helpers, pytest config, and tracked relevant package initializers. It contains only existing Git-tracked files; no `__init__.py` stubs or production data were added. Archive: 2,946 tracked files, 55,497,795 payload bytes, SHA-256 `93accd8d4582e6958c6a30d3c376caae16ecca0fa4342efc7cc01f938b458bb9`.

Before and after execution, all 2,946 extracted inputs matched their candidate Git blob IDs and SHA-256 values; the archive and canonical manifest hashes remained unchanged (`candidate-input-hashes.json`). The full path/blob/SHA manifest is retained in `candidate-input-manifest-before.json` and `candidate-input-manifest-after.json`. The archive command and its stdout/stderr are in `archive-command.json`, `archive.stdout.txt`, and `archive.stderr.txt`.

The test ran in the existing G `.venv/bin/python` (Python 3.14.3, prefix `.venv`), pytest 9.0.2 and pytest-benchmark 5.2.3. The pre-run environment profile was emitted directly by that interpreter, not inferred from an outer runner; its invocation and executable are recorded in `environment-before-command.json` and `environment-before.json`. `environment-after.json` records the post-run installed distribution set. An earlier environment-only inventory helper call used an unsupported `distribution(path=...)` argument and returned `TypeError` before writing any file or invoking tests; the corrected `distributions(path=[...])` query below is the preserved profile. SALib 1.5.2, multiprocess 0.70.19, and dill 0.4.1 came from the pinned ignored overlay prepared from `policy-engine/uv.lock`; no packages were installed into the G venv. Their distribution versions, overlay paths, `RECORD` SHA-256s, and direct wheel URLs are in `runtime-provenance.json`; the lock/hash install receipt is `../1800-doe-prerequisite.md`.

The same-process provenance wrapper observed 77 loaded `polisyos` modules, and asserted every origin resolves under this candidate's extracted `src/polisyos`. SALib, its Morris/Sobol sampler and analyzer modules, multiprocess, and dill resolved under the overlay. NumPy 2.3.5, SciPy 1.16.3, and pandas 2.3.3 loaded from the G venv. Matplotlib 3.10.8 was available by metadata/spec but was not imported by this selector. All provenance assertions are true; the complete module-origin set is saved in `runtime-provenance.json`.

## Property demonstrated and limit

The 77 cases are 72 combinations of eight mutations over nine materialization boundaries, plus five focused controls: real Morris and Sobol sample/analyzer oracles; the explicit `allow_large_run` positive override; a sampler mutating the original plan after snapshot; an adaptive evaluator mutating its source plan; and a removal probe showing that bypassing admission permits an over-cap native sample. The negative backend guards assert invalid mutated plans are rejected before any backend or evaluator callback.

This is evidence for the candidate's **per-design mutable-plan admission and explicit override behavior** at the tested boundaries. It does not establish a shared/server-wide budget, orchestration-level budget enforcement, production behavior, or closure of unrelated DoE findings. No test/product source was repaired and no broader suite was run.

## Resource and branch closeout

Before the run, G was clean at the SHA above, 13 GiB was free, system memory free was 47%, and no Python/pytest runner was active. After the run, 13 GiB remained free, system memory free was 53%, no matching pytest/runner process remained, and the branch/ref state was unchanged and clean (`after-state.json`, `slot-status-after.json`).

The extracted candidate source is 55,497,795 logical bytes / 62,005,248 allocated bytes, below the 100 MiB source bound. The retained source tar is 57,927,680 logical / 57,929,728 allocated bytes. Generated receipts, JUnit, pytest outputs, and temp data—counted separately from source/archive by unique inode—are 1,659,201 logical / 1,703,936 allocated bytes, below the 500 MiB generated-artifact cap. There were no extra files in the extracted source tree. Detailed counts are in `artifact-footprint.json`.

Everything is under ignored `policy-engine/_build/e02-g-continuation-20261006/R/1845-DOE-checks`; `git status -sb` remains clean. The test slot is released.
