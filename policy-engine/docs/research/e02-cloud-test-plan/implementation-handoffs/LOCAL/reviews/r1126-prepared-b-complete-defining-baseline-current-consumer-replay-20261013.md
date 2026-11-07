# R1126 Prepared-B current-source and timeout-wire review

**Verdict:** GO to root-run the exact current-source R1 batch for characterization after the shared source queue is frozen. The batch is not a closure. The timeout-wire claim remains an engineering verification gap until one portable test reaches the admitted Darwin spawn task, IPC result, changed-receiver merge, and property-removal control.

## Source binding

Current branch `codex/e02-unified-local-20261009`, HEAD `1ccb8368df94735006cbfd16d5bc2d220d8e66b4`, tree `aec287e84229ee2c20c3f88ab1ad057d543177a4`. The latest source frame is [`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/root-author-source-frame-r1134-20261013.json`] at SHA-256 `81b47b6e7f1cb846959aa7d711a8853c123d6eb194f9aa40ff8be3683a21e5ad`. I independently rehashed all 568 physical postimages: 568 match; no missing paths or mismatches.

The prior R1128 frame is `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/root-author-source-frame-r1128-20261013.json` at `da72001a1461c64ab7a2c7b4349e6a251bdc2a013d1d8ddcb4790d6bf446d392` (554 paths). R1134 has 14 added frame paths and the same HEAD/tree. None of the added paths intersects the exact 14 R1 test targets or the 19 principal source paths. The full path list is in the JSON receipt. Therefore R1117/R1131's newer stress/search work does not invalidate the R1 denominator or its selected source paths; it does not provide evidence for them either.

R1's exact inputs still match their pinned hashes. The current task says the prepared defining baseline, 13 named contours, and matched removals; no old0bf carry. The protected objects still resolve: defining baseline `2d3a990ff716b46ccf473e229b9de7e009a1d1fb` / tree `68ae933789c2160911260d769039757c7a142a58`; candidate `1e18a965b4334331dc3d5542b609f8a00bb35c6d` / tree `e711617c480101e5a7e8f9dd1fb23ab74e2c78ea`; handoff `a0ee451fb287d9666c620defd01fdc87ff864c60` / tree `677257974c442ba878a6bf4dba6686ae854b2e67`. Published PR55 delivery base `53b14a6e5af66f2a784d7f4981c4613e534acd40` is distinct; do not substitute it for the prepared source slice.

All current R1 target paths are byte-identical to HEAD and index and either match the R1134 frame postimage or are unchanged HEAD files:

- `policy-engine/tests/unit/scientist/orchestration/engine/test_state_branching.py` — `ed54168d41095cd81f000c45901460e45484f6ba8842c291c752f532dc8368fe`; 26 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/test_state_merge.py` — `44597a58ee34d703db68f189d03b6e7a99a5d7bbe7a9352ac8876241537e1648`; 21 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/test_native_state_cache_semantics.py` — `3278cd12581863fc133b746b68227ad94e694a18513fba5b2ed17dd25d9571b2`; 2 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/test_idempotency.py` — `8cc7f8ecf3a779f489e91e54a3f0ccf60df493bc9be63d1ebf49739e1d2235f5`; 26 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/test_engine_executor_idempotency.py` — `9f87c306b83b8b9e397685e05aedde96291e35b2a846dd5f4161ec94aadc4703`; 8 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/test_async_cache_recovery.py` — `3bf81925e005c386889c6df80f48f5319fd741cd95ea0a65bacdd19a5de820ee`; 8 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/test_cache_reference_custody.py` — `08f7d895f640625f74090ec1bf5c959b539e98974c7f92b41f793a630cceae9a`; 4 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/test_async_executor.py` — `68a3e35f641ef68333e8c7b2c604d7d154447e705a0430081ddf348f9b7f8f2b`; 15 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/test_async_executor_hardening.py` — `94b9cc60813d85b6a22e0f707d141d64d04ff2b219f13b3c2b4470a4219bf531`; 11 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_activity_worker.py` — `3ab9aa4c1e5f9e43a20e2d0e6c550d90a0fc8eb0bc40c7cd379d1280056d43e7`; 17 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_serialization.py` — `46e803f7a019ec5891cfdf278582159131cdf802fbf83479bbdf5dfc42476a18`; 26 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py` — `ea6579ebeafd7ef336ff2fe6af2cd3f5ceb87889952832c7185098226cde75ba`; 9 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_state_merge.py` — `316baf196fac8810bbf1894928d9472f3c6951f738a9edcff4eb67af2f4933b0`; 8 test defs
- `policy-engine/tests/unit/scientist/orchestration/engine/test_producer_scope_reconciliation.py` — `7ed69a33cb1b73057179fb52d1f10df8788c5c957fe27c8b0bbffb28f84416c7`; 6 test defs

The 13 affected contours plus the separately required producer baseline are:

1. `tests/unit/scientist/orchestration/engine/test_state_branching.py` — Declared nested-write isolation, finite producer-state graph admission, and copy-on-write branch behavior; source state_branching.py.
2. `tests/unit/scientist/orchestration/engine/test_state_merge.py` — Journaled parallel writes, conflict policy, and distinct set/delete/null/no-write replay through engine/state_merge.py.
3. `tests/unit/scientist/orchestration/engine/test_native_state_cache_semantics.py` — Native-state presence sensitivity across cache reopen/replay through engine/idempotency.py.
4. `tests/unit/scientist/orchestration/engine/test_idempotency.py` — Idempotency input identity, deadlines/scope, embedded outcome, mutation journal, epoch compatibility, and corrupt-entry refusal through NodeResultCache.
5. `tests/unit/scientist/orchestration/engine/test_engine_executor_idempotency.py` — WorkflowExecutor cache hit after reopen, compatible replay, incompatible target recompute, and failed-node noncommit.
6. `tests/unit/scientist/orchestration/engine/test_async_cache_recovery.py` — Async cold seed/recovery, late-read nonpublication, absolute workflow deadline, and durable cache publication via async_executor/checkpoint/retry.
7. `tests/unit/scientist/orchestration/engine/test_cache_reference_custody.py` — Selected CAS manifest-view identity, foreign-view refusal, and full ArtifactRef dedupe via cache plus Core CAS.
8. `tests/unit/scientist/orchestration/engine/test_async_executor.py` — Actual async DAG producer execution, cache boundary, budget/cancellation, and no partial CAS publication.
9. `tests/unit/scientist/orchestration/engine/test_async_executor_hardening.py` — Parallel branch isolation, savepoint rollback, merge conflict, timeout and budget effects.
10. `tests/unit/scientist/orchestration/engine/runner/test_activity_worker.py` — Worker store ownership/context preflight, declared operation replay, checkpoint, and native status preservation.
11. `tests/unit/scientist/orchestration/engine/runner/test_serialization.py` — Ordinary public state/outcome wire, typed reader, incomplete subtype refusal, and explicit legacy compatibility.
12. `tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py` — Real worker-process Decimal/ArtifactRef transport; non-finite, tampered, and untyped values refuse.
13. `tests/unit/scientist/orchestration/engine/runner/test_state_merge.py` — Worker-produced declared write journal and artifact-index merge conflict semantics.

Current AST counts yield 187 test function definitions across 14 Python files. These are target counts, not executed outcomes. The 19 principal source paths and current hashes are recorded in the JSON receipt.

## Timeout-wire gap

The candidate `1e18a965` version of `test_remote_worker_timeout_wire_replays_only_declared_branch_operations` passed a custom `JournalReplayWorkerNode` to `run_node_in_worker` with `timeout_s=2.0`, then deserialized and merged the outcome. On the current host's Darwin route, that custom node is refused by the closed spawn admission list. The current test avoids that route by using `timeout_s=None` on Darwin (2 seconds only on Linux); this proves the generic activity worker wire and merge, not timeout-process IPC.

The actual Darwin path is `execute_with_retry_sync/async` → `_execute_with_timeout_process*` → `_build_spawn_timeout_task` → typed `NodeTask` → `_typed_node_timeout_worker` → `_WorkerResultChannel` → caller/`merge_tier_outcomes`. The current admitted node is only `scientist.node_resolve_parameters@1.0.0`. Existing spawn tests prove cleanup, authority revocation, and unsupported-input refusal. The real SKG spawn integration proves source lineage. Neither proves that selected branch operations survive this typed process wire and affect a changed parent receiver, and no R1 path removes the operations while retaining wire markers as a falsifier.

**P38 divergence:** the property is declared-operation replay across actual timeout IPC into a changed receiver. The current R1 test measures generic direct worker serialization plus merge; on Darwin it disables timeout, and the Darwin spawn path only accepts a canonical built-in. That is a concrete counterexample at the boundary being qualified.

**Smallest companion:** add one test within the existing `runner/test_activity_worker.py` denominator that uses the canonical `ResolveParametersNode` with real `RunContext`/CAS input, drives the current timed process caller and typed task/result channel, and merges the outcome into a changed receiver. Assert declared set/delete effects and preservation of unrelated receiver values. Remove only the serialized mutation operations while retaining the other wire markers and assert divergence. Retain unsupported-node/context and no-fallback controls. This is `SAME_CLASS_DEEPER` under P40: widen the complete producer→IPC→consumer class, not another unit-level projection.

## Root-native batch

The current native batch is prepared, not run. It includes exactly the 13 contours plus separate producer baseline and has no `-k`, ignore, deselection, or early stop. Use fresh capture directory `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/prepared-b-r1126-current-composition-20261013` and retain stdout, stderr, JUnit, progress, module origins, and run metadata. Set the plugin modules explicitly; they are in the canonical LOCAL raw directory. Run from `policy-engine` after root freezes the queued source changes:

```sh
cd policy-engine
PYTHONPATH=src:docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 BLIS_NUM_THREADS=1 E02_PROGRESS_OUTPUT=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/prepared-b-r1126-current-composition-20261013/progress.json E02_MODULE_ORIGINS_OUTPUT=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/prepared-b-r1126-current-composition-20261013/module-origins.json .venv/bin/python -B -m pytest -o addopts= -q -ra --tb=short --color=no --maxfail=0 \
  --junitxml=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/prepared-b-r1126-current-composition-20261013/junit.xml \
  --basetemp=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/prepared-b-r1126-current-composition-20261013/pytest-basetemp \
  -p e02_progress_failure_r559_20261013 -p v5_single_thread_pytest_r315_20261012 \
  -p e02_runtime_module_origins_r792_20261013 \
  tests/unit/scientist/orchestration/engine/test_state_branching.py \
  tests/unit/scientist/orchestration/engine/test_state_merge.py \
  tests/unit/scientist/orchestration/engine/test_native_state_cache_semantics.py \
  tests/unit/scientist/orchestration/engine/test_idempotency.py \
  tests/unit/scientist/orchestration/engine/test_engine_executor_idempotency.py \
  tests/unit/scientist/orchestration/engine/test_async_cache_recovery.py \
  tests/unit/scientist/orchestration/engine/test_cache_reference_custody.py \
  tests/unit/scientist/orchestration/engine/test_async_executor.py \
  tests/unit/scientist/orchestration/engine/test_async_executor_hardening.py \
  tests/unit/scientist/orchestration/engine/runner/test_activity_worker.py \
  tests/unit/scientist/orchestration/engine/runner/test_serialization.py \
  tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py \
  tests/unit/scientist/orchestration/engine/runner/test_state_merge.py \
  tests/unit/scientist/orchestration/engine/test_producer_scope_reconciliation.py
```

R793 is historical only: it ran 326 outcomes at old HEAD `14683576597938efc1b01b7e2eeb8fe80b175721`, with 314 pass / 12 fail / 0 error / 0 skip. Ten were `run_start_existing_lifecycle`; the remaining two were invalid positive registry/CAS test fixtures (R796). Current `test_activity_worker.py` and `test_serialization.py` contain the real `build_default_registry_bundle(..., return_selected_profile=True)` path, but the exact R1134 suite has not been run. `RunContext.start` terminal reuse still follows G choice R448, which is author-packet-only and unresolved; do not change run IDs or call expected refusals a defect. R1 does not close B61 same-path source binding or B148 import preservation; both keep their own criterion routes.

R1 remains `verification_missing` pending the current complete run, module-origin receipt, and matched removals. `closure_ids=[]`.

Independent receipt: `r1126-prepared-b-complete-defining-baseline-current-consumer-replay-20261013.json` (`/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/reviews/r1126-prepared-b-complete-defining-baseline-current-consumer-replay-20261013.json`; unavailable in this checkout).
