# G-local D ask/CAS receipt: independent read-only check

Review base: G `ff277db7798fc312654704fa51c52e00f53f10f4`; no tests were run. Candidate `8c17a44c6f6ce8fe1b3dc334a689fb6cb05a6e47`, tree `4b0b58cc1fe0d7faab3d7aec49f99519dd080459`.

## Input and execution identity

- Final manifest `G-D-ask-checks/source-manifest-attempt2.json` SHA-256 `fada274e…` binds 2,941 tracked blobs / 56,200,179 bytes. Context verifies all blobs/modes and no extras both before and after. The service and test hashes match the manifest and archive: `service.py` `5d966a54…`; `test_service_persistence.py` `27ca58db…`.
- Import-origin capture `results/module-origins-attempt2.json` SHA-256 `f2acfba7…`: all 830 loaded `polisyos` modules and 5 test/helper modules resolve inside the archive and match the manifest; zero outside/mismatched origins. This is runtime-import coverage, not proof about modules that were never imported.
- Exact runtime command, environment, package versions, candidate, timing, RSS and before/after source/G state are in `results/context-attempt2.json` SHA-256 `9a8ef0be…`. Pytest ran as `/.../policy-engine/.venv/bin/python -m pytest` with cwd in the archived candidate; `VIRTUAL_ENV` is unset, `PYTHONNOUSERSITE=1`, and `PYTHONPATH` names only candidate `src`, candidate `tests`, and the ignored origin-check harness. This was the actual G venv interpreter, not a wrapper selecting a different runtime. Sampled peak child RSS was 602,912 KiB; wrapper wall 9.76s (pytest 7.18s), 180s timeout not reached. There is a sampled peak, not a continuous profiler trace.

## Deciding output and property

- Raw attempt-2 stdout SHA-256 `b817ab5d…`: `2 passed, 0 failed/skipped` in 7.18s; one non-fatal `cache_dir` warning because pytest cache provider is disabled. Stderr is empty (SHA-256 `e3b0c442…`). Raw JUnit SHA-256 `b62d577e…` independently parses to 2 cases, 0 failures/errors/skips. The receipt’s bytes and hashes match all four files.
- The test uses production `NativeSearchService`, `SearchController`, `SequenceCandidateGenerator`, and actual filesystem `FileSystemCAS` on `tmp_path`. A healthy ask/tell persists an acknowledged checkpoint; then parameterized `fail_write` or `fail_readback` makes the next ask raise at the actual `put_json` or `get_verified_snapshot` seam. Assertions verify the service ref, generator cursor, ask iteration and pending IDs roll back; a new service + new `FileSystemCAS` instance restores the acknowledged ref and matches live history/state; after clearing the fault, both services produce equal `candidate_1_0`, `{"cost": 1}`. This tests produced, persisted and consumed state, not constructor shape or a marker.
- Fault injection is at the CAS method boundary, not OS corruption: `fail_write` raises before delegating to `FileSystemCAS.put_json`; `fail_readback` raises before the base read method, after the real base `put_json` has stored the artifact. Basetemp confirms that failed-readback candidate blob exists while `checkpoint_ref` stays at the acknowledged artifact. The test does not claim absence of orphan immutable CAS bytes, nor independent-process behavior.
- Bounded consumer is the direct native service helper (`_direct`) with a deterministic two-candidate fixture and simple stage-B callback. It does not exercise `SearchLoopRunner.create_service`/composed factory: that path remains `UNRUN`, not a new finding.

## Harness correction and generated residue

- Attempt 1 is a harness-closure error, not a product failure: both JUnit cases fail at import with `FileNotFoundError` for the tracked digest-domain TOML, before ask/assertions. Attempt 2 keeps the same candidate SHA/tree and adds the exact 19 omitted tracked files: 17 production-quality TOMLs, `uv.lock`, and `tools/devx/foundry/sync_dependency_profile.py`. Final archive/origin proof is sound for the declared closure.
- Attempt-2 deciding artifacts to preserve: `receipt.md`; `results/context-attempt2.json`, `pytest-attempt2.stdout.txt`, empty stderr, `pytest-attempt2.junit.xml`, `module-origins-attempt2.json`, and `source-manifest-attempt2.json`. Their exact paths and hashes are above / in the receipt. Keep attempt-1 stdout/JUnit/context and `source-manifest-before.json` only if retaining the harness-error provenance.
- Reproducible disposable footprint, after preserving receipts: `candidate/` 56,200,179 bytes; `harness/` 31,199 bytes; `results/` 999,737 bytes. `results/pytest-basetemp-attempt2/` is 26,626 bytes: 6 real checkpoint blobs (18,814 B), 12 manifests (7,812 B), 8 zero-byte locks. Failed attempt’s `pytest-basetemp/` is only two zero-byte locks. Nothing was deleted or moved.

Independent result: the exact direct-service ask rollback/readback property is supported by the pinned passing run. This does not accept a broader D claim or close a finding.


Publication scope: this is a pinned review observation/recommendation. A bounded GO here is not an integrated commit or formal finding closure. The root decisions in the eighth-wave README and newer per-unit audit take precedence for later heads.
