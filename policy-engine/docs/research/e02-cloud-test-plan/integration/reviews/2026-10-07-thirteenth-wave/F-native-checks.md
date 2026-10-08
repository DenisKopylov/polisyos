# F local exact-candidate checks — 2026-10-07

Verdict: **PASS for these two scoped checks only**. This does not accept the full F slice, close findings, or establish causal identification.

## Pinned source and environment

- Candidate: `4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d`, tree `551d4e760dc1168f6ad8182c9b176f00e94a2281`.
- Exact export: `/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos/policy-engine/_build/e02-g-continuation-20261006/R/integration-1722-20261007/native-F/candidate`; source manifest: `/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos/policy-engine/_build/e02-g-continuation-20261006/R/integration-1722-20261007/native-F/source-manifest.json` (`sha256 10e138869e00af15ec39bb1b059b96aa6f6dd7c7fde9280a3a6f238eba979f18`). All 2,942 manifest files and executable modes matched their pinned Git blobs before and after the deciding runs.
- Existing G virtualenv, Python 3.14.3, pytest 9.0.2, macOS ARM64. No package installation or production data. The benchmark identifies its input as `synthetic_policy_natural_experiments`; optional comparator versions are all null and are not covered.
- G remained attached and clean at `codex/e02-integration` HEAD `9806442ddb47d624a2940bac75d9d6248e934c48`, tree `4a1caafc331990e0ebf0130a9051c08ae1ffcbd4`.

## Graph producer/consumer check

The existing selector in `tests/unit/scientist/methods/causal/test_graph_intake_current_content.py` ran **9 passed, 0 failed, 0 errors, 0 skipped; 38 deselected**. Wall time was 13.105 s; peak sampled RSS was 620560 KiB. The current-content test exercises synthetic `build_mgraph` output through the registered reconciliation method, `MethodJob`, the node, CAS, and a fresh `FileSystemCAS` reader: unsupported MGraph/CPDAG/PAG shapes are refused without publication or retyping, while the corresponding supported ADMG shape round-trips; supplied-result and selected-cache inputs do not bypass the profile boundary. The fresh reader is a new instance in the same process. This does not classify real-world missingness or assert causal authority.

Origin audit: 970 loaded `polisyos`/`benchmarks` modules, all bound to candidate Git blobs, zero errors. Pytest emitted one harness warning (`Unknown config option: cache_dir`) because the command disabled its cache plugin; selected tests still passed.

## Synthetic DiD smoke

The benchmark command returned 0 in 7.097 s; its JSON reports **3/3 passed**, 0 failures/errors/skips. `clean_rollout` reports estimand `ATT` with 2 pre-periods. Its pretrend diagnostic is `not_testable` / `insufficient_pre_periods`, with `passed=false`, `statistic=null`, `p_value=null`, and `identification_authority=false`. The result expressly does not establish identification.

Origin audit: 773 loaded product/benchmark modules, all exact-candidate-bound, zero errors.

## Generated output and harness event

The graph test emitted one 8,475-byte runtime artifact at `/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos/policy-engine/_build/e02-g-continuation-20261006/R/integration-1722-20261007/native-F/candidate/policy-engine/src/_build/benchmark-results/foundry/selection_history/executions.jsonl` (SHA-256 `62cec7214e5fc59b92facaf7bf56b67048cf2205aec084b793d68e842e441a62`). It is outside the tracked-source manifest, and its hash stayed unchanged during the DiD run. The first orchestration wrapper stopped before starting DiD because its whole-export inventory check treated that runtime output as an unexpected file. That was a harness stop, not a test failure. A separate exact-source check verified every pinned blob/mode, allowed only this known output, and then ran DiD; no file was removed.

Complete stdout, stderr, JUnit, machine receipts, full import-origin audits, and benchmark JSON are preserved in `/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos/policy-engine/_build/e02-g-continuation-20261006/R/integration-1722-20261007/native-F/results`. See `receipt.json` for paths and hashes.

## Published evidence navigation

[outputs.json](outputs.json) binds complete committed moderate deciding bytes; [F installed evidence](F-installed-surface.md), [F exact native checks](F-native-checks.md), [F metadata diagnostic](F-native-metadata-diagnostic.md) and [E diagnostic](E-native-diagnostics.md) give scope. Raw `_build`/native-results paths above are historical local receipt locations, unavailable to a cloud reader as filesystem paths. Large origin inventories, source manifests and harnesses are retained locally with hash refs, not copied into Git; no production proof is inferred from them. Published F smoke data: [result](outputs/F-DiD-result.json), [semantic verification](outputs/F-DiD-semantic-verification.json), [scoped receipt](outputs/F-scoped-receipt.json).
