# Zero-debt exception retirement evidence

This is a narrow cleanup of current exceptions whose measured property no longer needs them. It does not renew or waive any issuer decision, move a date, change a floor, or rewrite historical baselines.

## Full current ratchet denominator

The complete report was run from `policy-engine/` with:

```text
uv run --no-sync python tools/quality/testing/report_test_ratchets.py --format json --fail-on-regression
```

The current full JSON output is retained at `LOCAL/raw/retired-zero-debt-rows/ratchets-current-retired.stdout` (113,069 bytes, SHA-256 `131818b95dd10a00dcbb30711744b28f48be23e74cf7eda8df5f03573deab43c`). Exit 1 is the current report result. The report walks 13 package rows and 2,400 current source modules; both current mirror numerators and ratios are shown here, with the complete payload retained above.

| Package | Current source modules | Loose mirrored / ratio vs floor | Strict mirrored / ratio vs baseline | Report status |
|---|---:|---:|---:|---|
| berl | 26 | 10 / 0.3846 vs 0.3846 | 1 / 0.0385 vs 0.0385 | explicit_exception |
| calibration | 8 | 6 / 0.7500 vs 0.7143 | 6 / 0.7500 vs 0.7143 | explicit_exception |
| common | 13 | 8 / 0.6154 vs 0.7778 | 4 / 0.3077 vs 0.3333 | floor_regression |
| core | 180 | 91 / 0.5056 vs 0.4824 | 35 / 0.1944 vs 0.1471 | below_first_target_tracking |
| data_forge | 252 | 152 / 0.6032 vs 0.6123 | 67 / 0.2659 vs 0.2291 | floor_regression |
| ddm | 14 | 9 / 0.6429 vs 0.6667 | 0 / 0.0000 vs 0.0000 | floor_regression |
| fabric | 259 | 130 / 0.5019 vs 0.5020 | 19 / 0.0734 vs 0.0717 | floor_regression_exception |
| foundry | 535 | 382 / 0.7140 vs 0.7176 | 187 / 0.3495 vs 0.3531 | floor_regression_exception |
| ir | 174 | 106 / 0.6092 vs 0.6012 | 25 / 0.1437 vs 0.1272 | below_first_target_tracking |
| lex | 40 | 22 / 0.5500 vs 0.4412 | 11 / 0.2750 vs 0.2059 | explicit_exception |
| runtime | 313 | 183 / 0.5847 vs 0.7152 | 123 / 0.3930 vs 0.3892 | floor_regression_exception |
| scholar | 24 | 11 / 0.4583 vs 0.4783 | 4 / 0.1667 vs 0.1739 | floor_regression |
| scientist | 562 | 380 / 0.6762 vs 0.7099 | 225 / 0.4004 vs 0.4120 | floor_regression |

The report's other current summary findings are 5 floor regressions, 2 strict mirror regressions, and 3 test-helper topology count regressions (24 shared helpers, 27 layer-local conftests, 1 duplicated fixture factory, 11 forbidden reverse imports, 1 unused helper). These remain open; this cleanup does not change them.

## Ratchet rows retired and retained

I removed only these complete exception tuples from `architecture/tests/ratchets.toml` (the boolean and its owner, expiry, reason, and issue fields):

| Row | Current property without exception | Decision |
|---|---|---|
| `fabric.strict_mirror_regression_exception` | Strict ratio 0.0734 is above 0.0717. The separate loose exception remains necessary because 0.5019 is below its 0.5020 floor. | Retired strict tuple only. |
| `ir.mirror_regression_exception` | Loose ratio 0.6092 is above its 0.6012 floor. The package remains `below_first_target_tracking` because its 0.70 first target is a different property. | Retired loose tuple only. |
| `lex.strict_mirror_regression_exception` | Strict ratio 0.2750 is above 0.2059. The package's independent `package_mode = "explicit_exception"` remains unchanged. | Retired strict tuple only. |

The current Scientist strict ratio is 0.4004, below its 0.4120 baseline; its strict exception was retained. Its loose ratio is also below floor (0.6762 vs 0.7099), so no strict-removal inference was made from the older denominator. Foundry's loose and strict ratios (0.7140 vs 0.7176; 0.3495 vs 0.3531), Runtime's loose ratio (0.5847 vs 0.7152), and Fabric's loose ratio (0.5019 vs 0.5020) also still need their respective live exception fields. No other exception was changed.

For the current denominator, the deciding report was run once with the three tuples absent, then three controls restored exactly one tuple at a time in scratch TOML files under ignored `LOCAL/raw/retired-zero-debt-rows/`. All four commands used `--fail-on-regression`; each exited 1 with the same full package rows, summary, and helper-topology payload. The retained current outputs are `ratchets-current-retired.stdout` and `ratchets-current-control-{fabric-strict_mirror_regression_exception,ir-mirror_regression_exception,lex-strict_mirror_regression_exception}.stdout`; the comparison and each output hash are in `current-source-control-manifest.json` (SHA-256 `6285f7a4e381af1c8cbcc8a41639b309c15d07c565528e8b134093c93f8e5f2b`). Each control records `same_full_payload_as_retired: true` after excluding only the contract path and report timestamp. This confirms these three fields do not affect the current deciding result; the unrelated failures above remain present.

The first post-edit report comparison observed a concurrent root-owned edit that moved the recorded usage line for `tests/_helpers/controlled_candidate_profile.py` from 2121 to 2130. I reran the full current report and all three tuple-restoration controls after that edit; the final manifest above is from that refreshed snapshot.

`tests/repo_quality/architecture/test_test_ratchets_contract.py` remains 3 passed / 1 failed at `test_phase_6_2_reporter_renders_package_mirror_and_property_summary`, which expects `floor_regressions == 0` and now observes 5. The current live report has the same summary with and without each retired tuple. I am not classifying this red as inherited or resolved: the changed ratchet contract is itself an input, so the P41 zero-input-intersection test does not apply. The one-tuple controls show no semantic output change, and the remaining ratchet repair is still open for its owner.

## `errors` rename-backlog row retired

I removed only the `[[rename_backlog]]` entry for `data_forge` at `src/polisyos/data_forge/domains/catalog/fixtures/academic/errors` from `architecture/name_registry.toml`. The old directory and the proposed `academic_error_cases` destination are both absent. A complete Phase 0 inventory reports 52 repeated-directory-name rows and zero rows named `errors`; its 55,101-byte full output is retained as `LOCAL/raw/retired-zero-debt-rows/phase0-inventory-after.stdout`, SHA-256 `55328377d8cfed33c5e5af0dc35c6d01460958a24c397f24d955711a360d6558`. The pre-removal inventory is byte-identical.

The complete scoped source/test reference scan used:

```text
rg -n -S 'catalog\.fixtures\.academic\.errors|academic/errors|academic_error_cases|fixtures/academic/errors' src/polisyos tests
```

It returned no matches (exit 1, empty output). The actual fail-closed `name_collision_gate.py --json` returned `{"findings": [], "mode": "fail-closed"}` both before and after row removal; both complete outputs are 46 bytes with SHA-256 `e26fdcc8bf34499fef3a20dd662a02eb3fd886e66a6495477df2353de00ef426`. `tests/repo_quality/architecture/test_repository_structure_phase1c.py` passed all five tests, including the current-collision consumer check and the negative unregistered-collision control. The existing `shared_name` entry for `errors` remains unchanged and still allows only `core`.

The historical inventory and repeated-directory baselines under `architecture/baselines/structure_remediation/` still contain their original recorded path and were not edited. No test pins the removed backlog row or its count.

## Classification and preservation

P40 classification: **same class, proven zero-current-debt exception/backlog rows**. The repair is limited to exact fields whose current measured predicate no longer uses them; fields still needed to keep live regressions explicit remain in place. The name gate continues to fail closed for a newly introduced unregistered collision, so this is not a blanket namespace allowance.

P35 evidence uses the complete package and directory-name inventories, not sampled paths. P29 is exercised by the existing negative name-collision test. Historical baselines remain historical evidence, not live consumers. The earlier `/tmp/dx0-{fabric,calibration,ir}-unignored.txt` outputs were copied byte-for-byte into ignored `LOCAL/raw/retired-zero-debt-rows/`; the originals remain present. No source code, test, floor, baseline, expiry date, or generated artifact was changed.

Worktree file hashes after these edits:

| File | SHA-256 |
|---|---|
| `architecture/tests/ratchets.toml` | `88a9a3595f82e7456fd483140aadcc1ef051dfc05b4375dfef1db87381f27792` |
| `architecture/name_registry.toml` | `ea985c079e393ca7fb98a89464dc3bbacff17ac453124e0ef18c89408707d842` |
