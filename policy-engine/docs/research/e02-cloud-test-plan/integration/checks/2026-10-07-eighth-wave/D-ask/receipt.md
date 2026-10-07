# G local ask/CAS rollback check

**Result: PASS, 2/2 parameter cases.** No finding closure or broader SearchLoopRunner-factory claim is implied.

## Pinned input and isolation

- Candidate: D root `8c17a44c6f6ce8fe1b3dc334a689fb6cb05a6e47`, tree `4b0b58cc1fe0d7faab3d7aec49f99519dd080459`.
- Source was materialized with `git archive` into `candidate/`; no `.git`, dependencies, or production data. Exact supplemental closure was added after attempt 1 exposed a missing tracked import-time registry: `policy-engine/architecture/production_quality/`, `policy-engine/uv.lock`, and `policy-engine/tools/devx/foundry/sync_dependency_profile.py`.
- Final source manifest: `source-manifest-attempt2.json`, SHA-256 `fada274e6b224df099a18380edbf2568f5f441a468875f8c216a9c00ea32e93e`; 2,941 tracked blobs / 56,200,179 bytes. Git blob IDs, modes, and SHA-256s all matched before and after; no unexpected candidate files appeared.
- Tested service source `policy-engine/src/polisyos/scientist/methods/search/service.py`: blob `c836b4d11ccf1f7fa18b373ffbf16884a9561106`, SHA-256 `5d966a542e590936b2e162594c4c1f987422f8333e255b34e432ca17d46bf7b9`. Test source `test_service_persistence.py`: blob `51ab4ce016ecf132bcbd61c6b9292d3bbc7429a4`, SHA-256 `27ca58db276560aa8dec8f19684aebcb0cf638f6111bd258340fefbbd757d7e3`.

## Exact run and evidence

Command was the G venv Python 3.14.3 running pytest 9.0.2 from the archive product root, with `PYTHONPATH` set to archive `src`, archive `tests`, and the ignored origin-plugin harness; `PYTHONNOUSERSITE=1`, bytecode disabled, and OMP/MKL/OpenBLAS/NumExpr/VECLIB threads set to 1. The exact argv and environment are in `results/context-attempt2.json`.

Selector: `tests/unit/scientist/methods/search/test_service_persistence.py::test_failed_ask_publication_restores_cursor_ids_and_last_acknowledged_fresh_view` (both `fail_write` and `fail_readback` parameters). Output: `results/pytest-attempt2.stdout.txt` (SHA-256 `b817ab5d3f0264104de117d586c6b8c709061a2219bf23c0252134b5a8f1d56a`); stderr empty; JUnit `results/pytest-attempt2.junit.xml` (SHA-256 `b62d577e83acc0d428f255bb1e72188bf0bdc82d992e552eb9ff243c0bfb4e85`). Pytest reported **2 passed, 0 failed/skipped** in 7.18s; wrapper wall 9.76s, max sampled child RSS 602,912 KiB. One `PytestConfigWarning` says `cache_dir` is unknown because `cacheprovider` was disabled; it did not affect collection or outcomes.

Both cases first create and acknowledge a healthy ask/tell checkpoint, then force the actual CAS write or verified-readback failure on the next ask. Assertions confirm the acknowledged ref, generator state, ask index, and pending IDs roll back; a fresh reader restored at that ref matches live history/state; after clearing the fault, live and fresh next proposals are equal (`candidate_1_0`, payload `{"cost": 1}`). This is a direct `NativeSearchService` check using `_direct`, as the requested selector specifies.

Origin capture: `results/module-origins-attempt2.json` (SHA-256 `f2acfba71e381b5ff7b15723832e7c3f921437edd6636d5f473a843aa2744ab4`) verified **830 `polisyos` modules and 5 test/helper modules** all resolve inside the isolated archive and match its Git-bound source manifest. In particular `service.py`, `controller.py`, and the test file resolve to the pinned archive blobs above.

## Harness correction and scope

Attempt 1 (`results/pytest.stdout.txt`, JUnit `pytest.junit.xml`, `context.json`) failed both cases before an ask/assertion because the initial archive omitted the tracked digest-domain registry TOML. It is retained as a harness-closure error, not counted as a product failure. The only retry used the same candidate SHA/tree and the exact tracked supplemental inputs identified by the import stack.

G stayed clean on `codex/e02-integration@ff277db7798fc312654704fa51c52e00f53f10f4` (tree `618e17b5da96a623d5e57f30d265e245a2b277eb`) before and after. System disk free was about 11 GiB; memory-pressure free percentage was 52% before and 50% after. No production data, installed dependencies, tracked source, tests, refs, or managed worktrees were changed. The check establishes the requested low-level CAS ask rollback property on this exact service/test source; it does not replay the separate SearchLoopRunner factory path or settle LA-014/LA-015/B109.

Publication storage: the named original stdout/stderr/JUnit files below results/ are lossless members of deciding-output.json; contexts retain their original paths as historical execution identity. Decode utf8 and verify bytes/hash to recover exact outputs. The originals remain in ignored G scratch.
