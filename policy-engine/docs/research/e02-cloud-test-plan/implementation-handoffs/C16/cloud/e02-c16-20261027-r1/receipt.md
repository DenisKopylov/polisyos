# C16 typed Foundry input author receipt

Task token: `e02-c16-20261027-r1`. Author result only; `closure_ids=[]`. G acceptance and formal closure remain separate.

## Source and environment

- Actual cwd: `/workspace/polisyos`; attached branch: `work`.
- Pinned base commit/tree: `8db01b1076e425b7998b05a658776c991b7bd594` / `1706923ebe943f1a332dca4860cd145ddd366e36` (both matched).
- Mechanism-test diff SHA-256 (the two leased tests, unified diff from base): `4fa33ef47fb46d59780229c39276a87e87cfc7d83334845b8c020d57b53ceb26`. Final commit is the commit containing this receipt; the delivery recipe is `git show --stat --oneline HEAD` and `git diff 8db01b1076e425b7998b05a658776c991b7bd594..HEAD`.
- Leased base file SHA-256 values matched the task: treasury `98a9a099...cf3efc9`; fiscal replay `b41dc8ef...31b1a00`.
- Disk: 32 GiB total, 28 GiB available; RAM: 17 GiB total, 16 GiB available; CPU: 3 logical processors.
- Cloud venv: CPython 3.14.4, pytest 9.0.2, JAX/JAXlib 0.8.2/0.8.2, CPU backend, x64 disabled. Host `pytest --version` was 9.0.3; tests used `.venv/bin/python`.
- Actual model/service identity was not established by the runtime and is therefore not asserted.

## Changed footprint and input chain

Material A delivered here comprises the two leased test changes plus this receipt, base-red stdout, complete repaired stdout, and JUnit XML. No product, schema, generator, lock, or unrelated test was changed.

The fixture writes now obtain Trinity, DataSnapshot, and FoundryInputBindings schema names and versions from each model's `ARTIFACT_SCHEMA_*` declaration while retaining the existing kind, media type, source binding, CAS, compiler, public executor, and fresh `FileSystemCAS` consumer. Fiscal replay derives the oracle's key from the compiled ProgramGraph and persisted TreasuryPlan, folds both 32-bit salt words, preserves the executor's split, then checks the complete state and mechanism PRNG progression.

## Results

- **PASS** affected modules: 33 passed in 52.51 s. This includes seed `None`, zero, 17, and high-word `2147483655`; historical plans; repeat and storage permutation; public fresh-store reads; registered dispatch; skipped-prior-draw invariance; active/inactive fiscal/labor state; employer and government balance leaves; and PRNG progression.
- **PASS** bridge removal parameters: `all_salts`, `high_word`, and `stream_salt`; the control and each removal executed in the 33-test output.
- **PASS** adversarial profile/content cases: unknown/duplicate profile, missing/duplicate treasury input, wrong plan/program links, wrong treasury source, wrong root/node/stream salts, missing/extra node, wrong kind, and wrong schema. These remain real fail-closed executions before the kernel.
- **FAIL (base fixture, repaired)** exact base selector first failed at `canon_profile_typed_artifact_schema_name_mismatch`, before execution. The captured parameter was `[None]`; pytest stopped after that first failure as required.
- **WARNING / tooling UNRUN** Ruff was unavailable in the cloud venv (`No module named ruff`); `git diff --check` passed.
- **UNRUN by bounded reuse** unchanged C12 randomization/precision/FRY-03 broad modules were not rerun because their source, inputs, and CPU JAX backend were unchanged. The affected modules provide the necessary post-repair discriminator.
- **UNRUN / not claimed** LA-003 ABM/P41 diagnostic and complete input-intersection proof were not run, so no ABM/P41 disposition is claimed.
- **Preserved external observation, not an inherited-red claim:** `test_runtime_consumers_use_exact_admitted_foundry_facades` reportedly has the base mismatch of four actual EstimandSpec imports versus one expected. It was not run or edited here; no LA-037 closure is claimed.

## Commands and evidence

1. Base red: `JAX_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest tests/unit/foundry/compile/test_treasury_execution.py::test_compiled_seed_and_persisted_salts_drive_actual_native_kernel --maxfail=1 -q`.
2. Deciding repaired run: `JAX_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest tests/unit/foundry/compile/test_treasury_execution.py tests/unit/foundry/execute/mechanisms/test_fiscal_labor_replay.py --junitxml=.../affected-modules.junit.xml`.
3. Static whitespace check: `git diff --check`.
4. Attempted lint: `.venv/bin/python -m ruff format ... && .venv/bin/python -m ruff check ...` (environment ERROR before execution: Ruff absent; it made no edits).

Deciding witness hashes are reproducible with `sha256sum` in this directory: JUnit `816a629a...c4831`, repaired stdout `030cdb55...76c8`, base stdout `96f44f47...c6adf`, and empty base stderr `e3b0c442...b855`.

Pattern closeout: this repairs P31's class of invalid typed fixture writes for the complete in-scope producer-to-CAS chain, uses behavioral owner execution rather than P29 markers, and does not promote unproved inherited failures (P41). No historical bytes or authority were fabricated.
