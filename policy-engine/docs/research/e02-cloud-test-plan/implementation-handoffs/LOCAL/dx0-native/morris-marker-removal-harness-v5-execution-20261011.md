# Morris V5 source-bound execution handoff

Status: **executed; bounded behavioral evidence recorded.** This is an execution handoff, not a closure decision. The V5 preparation note and V3 failure record remain preserved as historical records.

## Run and source boundary

The harness ran from the product root at `19b0486608f0c134fcbff174c88d32fef82edafe` (`b193643df4dcc876b1ccb8202411db099610f79e`, parent `297b0557511234bb4b1bd3b09991cef0bd050a3f`). Its argv was:

```text
.venv/bin/python -B docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/morris-marker-removal-harness-v5-20261010.py
```

The command exited 0 in 28.7369 seconds. All six child commands completed under their 60-second bound; there were no timeouts. The source fence compared 6,159 paths before and after, with identical path sets and zero byte-hash changes. The six source/test inputs used by the probes are recorded with SHA-256 values in the companion JSON.

The production/source test checkpoint is commit `297b0557511234bb4b1bd3b09991cef0bd050a3f` (tree `ad9ecc1c4bf2acd57b187b5a2534aa9f3b2d3ffd`, parent `7e9d0912e014252260c217396ba50465392ab69a`). The executed harness content is SHA-256 `dcc96f1a27448bcb7f8e3fa6b92c4581990f0d4cf89c4b7f451b76df1b8fd50f`; it was subsequently checkpointed at `e057fa0ae6b92fbc9a9722da3d61fc40b8233084` (tree `4bce2e4f40240b0346b40d7a14e15dabae90b305`, parent `19b0486608f0c134fcbff174c88d32fef82edafe`). Local and remote readbacks bind that checkpoint to the same bytes. The run remains attributed to its actual base, `19b0486608f0c134fcbff174c88d32fef82edafe`, rather than retroactively to the later harness checkpoint.

## Deciding results

The retained JUnit files contain 18 cases: 8 intact-control passes, 10 expected mutant failures, 0 errors, and 0 skips.

- Both Morris mutations were detected by the real three-dimensional-chain selector: replacing the tensor slot with a matrix violated the `parameter_levels` contract; removing the 3D elementary-effect assignment violated the computed-effect assertion.
- The intact final-consumption validator rejected all six malformed sync/async inputs before the consumer ran. Removing that validator caused all six typed rejection assertions to fail after six real consumer dispatches.
- The intact ragged-coercion path rejected both sync/async values before dispatch. Replacing the recognized coercion exception with `return None` sent both malformed values into the real consumer; both then failed outside the typed validation stage, with two recorded consumer dispatches.

The outer stdout and nested `result.json` are retained with SHA-256 `a3a8e7a34064664c982edfa4de71d6aa0c3ea380120549cc14fd73562e05ae66`; outer stderr is empty. The six JUnit files and their full child logs are under the nested run directory cited in the JSON.

## Decision boundary

P40 bucket: **SAME_CLASS_DEEPER**. V5 widens the final-consumption behavioral probe to include both validator removal and the recognized coercion-failure-as-absence escape, across sync and async consumers. The mutations preserve the surrounding markers and invoke the actual chain/consumer path, so these results distinguish runtime behavior from marker presence.

Proposed disposition remains **limited**. The run establishes only the selected Morris 3D checks and the selected supported array-like final-consumption paths. Opaque multi-slot mappings and custom materializers without an exercised value-to-slot projection remain **not_established**. `closure_ids` is empty; this handoff makes no formal closure claim.

The V3 run remains separate and invalid as property evidence: its generated `sitecustomize.py` raised `SyntaxError: unterminated string literal`, so both child processes exited without applying the mutation. Its stdout SHA-256 is `a80b7958d9a613d2aa7f4555e99ce295737a4d632d5fb86a2cdf0dcf3583960e`. V5's actual outputs are retained separately.

## Evidence files

- Canonical structured record: `LOCAL/dx0-native/morris-marker-removal-harness-v5-execution-20261011.json`
- Full outer command/output: `LOCAL/raw/batched-blocking-focused-20261010/morris-v5-real-chain-rank-coercion-marker-preserving-removals/`
- Full child result/JUnit/logs: `LOCAL/raw/morris-marker-removal-harness-v5-20261010/run-20261010T235510Z-8208/`
- V5 preparation record: `LOCAL/dx0-native/morris-marker-removal-harness-v5-20261010.md`
- Independent static review: `LOCAL/reviews/morris-marker-removal-harness-v5-independent-20261010.md`
- Preserved V3 failure record: `LOCAL/raw/batched-blocking-focused-20261010/morris-v3-real-chain-marker-preserving-removals/`
