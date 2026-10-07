# A11 focused default-NCM check receipt

**Verdict: PASS for this focused selector only.** Candidate `905820ceac5860c7d1c4ebcbdde7b1265afb0b15` (tree `98405fab6c567d9fd44a5e30387c0ba32a7c7cf9`) passed all 11 cases in `tests/integration/core_runtime/test_e02_hard_feasibility_before_voi.py`. This does not establish full A acceptance, production-data grounding, served API behavior, or closure of broader N5 findings.

## Exact source and execution

The candidate was materialized into an isolated Git-archive checkout, not tested from the moving integration worktree. The second closure contains 2,933 Git files / 55,580,566 source bytes (under the 100 MiB cap). Every selected file matched its candidate Git blob hash before and after the run. The parent test process observed 1,468 `polisyos` file origins; every origin was under the candidate `src/polisyos` and matched its exact Git input hash. The fresh N8 subprocess independently reported its `generation_cycle.py` from the retry candidate checkout; its PID (78925) differed from the pytest process PID (78885).

The exact command was run from the isolated checkout’s `policy-engine` directory, using the existing G `.venv` and no dependency installation:

```sh
/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos/policy-engine/.venv/bin/python -m pytest -vv -p e02_a11_observer \
  -o cache_dir=/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos/policy-engine/_build/e02-g-continuation-20261006/R/1910-A11-checks/outputs/attempt2/pytest-cache \
  --benchmark-storage=file:///Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos/policy-engine/_build/e02-g-continuation-20261006/R/1910-A11-checks/outputs/attempt2/benchmark-store \
  --basetemp=/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos/policy-engine/_build/e02-g-continuation-20261006/R/1910-A11-checks/outputs/attempt2/basetemp \
  --junitxml=/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos/policy-engine/_build/e02-g-continuation-20261006/R/1910-A11-checks/outputs/attempt2/a11.xml \
  tests/integration/core_runtime/test_e02_hard_feasibility_before_voi.py
```

The project pytest config was preserved; only cache, benchmark-store, basetemp, and JUnit output paths were directed into the ignored receipt directory. The observed child environment and package profile are in `outputs/attempt2/execution-environment.json`. It used Python 3.14.3, pytest 9.0.2, pytest-asyncio 1.3.0, Hypothesis 6.151.2, NumPy 2.3.5, JAX 0.8.2, Pydantic 2.12.5, and SciPy 1.16.3.

Pytest collected 11 cases and reported `11 passed, 1 warning in 25.80s` (outer measured wall time 29.741 seconds, exit 0). The single warning is Pydantic’s serializer warning on the deliberately subclassed atom refusal case. JUnit confirms 11 tests, zero failures/errors/skips in `outputs/attempt2/junit-summary-corrected.json`; the complete unmodified XML and stdout are retained. The initial derived parser summary read the outer `<testsuites>` node and showed zero; `junit-summary-corrected.json` reads the nested `<testsuite>` count and agrees with pytest stdout. Raw command output was not changed.

The child N8 consumer returned `value_conditional`, the persisted value reference, and the authority blocker `simulation_only_k_sim_not_world_evidence`; complete raw child stdout/stderr and invocation record are retained. The module includes the direct negative discriminator: removing the N5 candidate filter while retaining the refusal marker makes the refused candidate selected and asserts N5 was not invoked.

## Attempts and resource bounds

Attempt 1 collected zero tests because the archive omitted `tools/lib/imports.py`, which the candidate `tools/lib/__init__.py` imports before loading `tools.lib.fs`. It is a setup/source-closure failure, not a product test result. Its full output is preserved under `outputs/attempt1`. The one authorized retry used a separate checkout/archive and added the four stdlib-only sibling modules explicitly imported by that initializer (`imports.py`, `output.py`, `preflight.py`, `sql.py`); no source, test, config, venv, or dependency was changed. Attempt 2 ran the same selector once and passed.

The attempt-2 process-tree peak RSS observed by the harness was 1,421,296 KiB; preprofile peak was 907,984 KiB. Attempt-2 receipt output files total 5,907,865 logical bytes. The ignored evidence directory occupies about 242 MB logical / 255 MB allocated bytes across unique inodes (the census excludes its own inventory file), including both isolated source checkouts and both tar archives; selected source itself is recorded separately in the source manifests. The initial checkout has no unselected generated files. The retry checkout contains three generated zero-byte `root.lock` files under `.polisyos/runtime/grounding_risk/` (exact paths and inode/stat evidence are in `../2020-A11-postrun-lock-residue.json`); they are absent from the candidate Git tree. All 2,933 selected candidate Git inputs still match before and after the run. These lockfiles add zero logical or allocated bytes. No production data was used.

At post-run capture, G remained clean on `codex/e02-integration` at `127dc7ab8365d29eb656fe32c0c894f6cc971286`; no pytest/verify process was active. The filesystem showed 12 GiB available.

## What this proves and does not prove

The result exercises the real `GenerationCycleController`, production `JointSimulationPort`, default N5/N8 owner route, persisted synthetic tenant-scoped CAS artifacts, a fresh N8 reader process, and the test’s removal-the-filter counterfactual. The all-infeasible path blocks before N5/VOI. It is a focused fixture-backed witness for default composition and the named negative discriminator.

It does not cover injected/custom controller factories, profile handoffs, custom request factories, actual served POST→GET, production N4 inputs, production grounding, or broad simulation/finding closure. Keep those limitations from the check plan separate from this bounded pass.

## Receipts

- `inputs/source-manifest-before.json`: attempt-1 exact candidate Git input inventory and hashes.
- `inputs/source-manifest-retry.json`: retry closure inventory, archive hash, and hashes.
- `outputs/attempt1/`: complete initial setup-error command, stdout/stderr, JUnit, and hashes.
- `outputs/attempt2/pytest-command.json`, `execution-environment.json`, `pytest-a11-run.json`: command, controlled environment, timing/resource sampling, and output hashes.
- `outputs/attempt2/pytest.stdout.txt`, `pytest.stderr.txt`, `a11.xml`: full deciding output.
- `outputs/attempt2/source-inputs-before.json`, `source-inputs-after-pytest.json`, `pytest-module-origins.json`, `pytest-module-origin-verification.json`: input and imported-source identity.
- `outputs/attempt2/n8-child-command.json`, `n8-child-stdout.jsonl`, `n8-child-stderr.txt`, `n8-child-verification.json`: fresh consumer process receipt.
- `outputs/attempt2/junit-summary-corrected.json`, `summary-corrected.json`: corrected derived result summary. `afterstate.json` and `resource-census.json` at this report’s directory record G state and bounded storage/resource measurements.
