# Helper-topology graph prototype (2026-10-10)

## Result

The current native gate is red on the declared helper-file ratchet: the reporter enumerates 23 Python modules under `tests/_helpers` against the active baseline of 10, a +13 count regression. It also reports zero unused helpers, zero forbidden reverse imports, zero unregistered duplicate fixture factories, and zero stale duplicate registrations; the one duplicated fixture factory in the baseline remains registered. The gate status is therefore `regression` because of the count predicate alone.

I ran one read-only source-derived graph prototype using the existing ratchet reporter's helper/conftest/test enumerators. It covered all 2,949 Python files under `tests/`, 2,822 test-named modules, all 23 counted helpers, 27 layer-local conftests, and the root `tests/conftest.py`. Its complete per-input hash manifest has 2,952 unique entries (the test-tree Python files plus the ratchet TOML, baseline JSON, and reporter source). The source-derived graph contains 12 helper-to-helper import edges. Following direct test imports, transitive helper imports, and pytest's ancestor-conftest activation yields 23 helpers with at least one static test consumer: 16 reach two or more test slices and 7 reach exactly one. There are no helpers without a static test consumer.

The 7 one-slice helpers are:

- `tests/_helpers/acquisition_human_decision.py` — one consumer: `tests/integration/core_runtime/test_acquisition_authority_served.py`.
- `tests/_helpers/acquisition_movement.py` — one consumer: `tests/unit/runtime/quality/test_acquisition_movement_positive.py`.
- `tests/_helpers/acquisition_supplier.py` — one consumer: `tests/unit/runtime/quality/test_acquisition_movement_positive.py`.
- `tests/_helpers/b61_timeout_worker.py` — one consumer: `tests/unit/scientist/orchestration/engine/test_skg_snapshot_replay.py`.
- `tests/_helpers/causal_scm_fixtures.py` — one consumer: `tests/unit/foundry/methods/test_sl5_fixture_coverage.py`.
- `tests/_helpers/runtime_api/legal_search_profile_fixture.py` — two consumers: `tests/unit/runtime/http/services/test_lex_pipeline.py` and `tests/unit/runtime/http/test_control_api.py`.
- `tests/_helpers/search_strategies.py` — eleven consumers, all in `unit/scientist`; their exact paths are listed in `graph-corrected-metrics.json`.

Their full consumer paths, along with every multi-slice helper's consumer paths, are in the raw report. “One slice” is a location signal for review, not proof of invalid sharing: the active contract only requires a helper to have a test, helper, or plugin consumer.

## Property and proxy

The implementation currently tests an explicit count policy: `len(tests/_helpers/*.py except __init__.py)` must not regress against the active baseline. That accurately answers whether the file count grew. It does not answer whether shared support is correctly placed, reused across test slices, or wrongly exposed as a shared helper. If the intended property is topology, the file count is a proxy:

- Countercontrol: add one valid helper consumed from two existing slices (`contract` and `e2e/demos`). The proposed cross-slice placement rule passes, but the current count becomes 24 and fails against 10.
- Countercontrol: keep the graph for the actual one-slice `acquisition_human_decision.py` helper and substitute count 10. The current count predicate passes; a proposed rule requiring shared-root helpers to serve multiple slices fails.

These are in-memory controls, not source or baseline mutations. The second proposed rule is not present in the active contract and must not be treated as a current violation. The contract owner and baseline owner are both `team-quality`, with `growth_policy = "ratchet_update_required"` and `mode = "fail_closed_no_regression"`. The narrow owner decision is whether 10 is a ratified ceiling that should continue to block growth, or a historical baseline for a topology property that should instead be measured from consumer edges. If the count remains policy, keep the present red until the owner adjudicates the +13 growth. If topology is the policy, the owner must define whether “shared” means more than one test slice or the current weaker “at least one consumer,” and decide how single-slice helpers and root-conftest imports are placed. No baseline update, exception, expiry change, or acceptance is made here.

## P40 / P41

**P40: SAME_CLASS_DEEPER.** The count red is the same count-versus-topology proxy class at a deeper level: filename totals omit transitive helper imports and the actual tests that inherit helper imports through ancestor conftests. Reuse the existing enumerators and contract, extend them to the transitive helper/conftest consumer graph, then consolidate that graph into the canonical report consumed by the gate. The current reporter only computes direct helper usages for its unused check; it does not provide a reusable transitive test-to-helper/conftest graph. The prototype demonstrates that the graph can be derived from the existing source tree, but static AST does not execute dynamic imports or runtime fixture registration. Those remain an explicit limitation if the owner chooses a graph-based policy.

**P41: NOT ESTABLISHED.** The task supplied HEAD `9194`; I did not query Git. I did not replay the exact gate from the slice base or establish a zero intersection between changed paths and the complete input set. This report does not classify the current red as inherited or newly introduced.

## Evidence and limitations

The raw artifacts are under `LOCAL/raw/helper-topology-prototype-20261010/`:

- Full deciding JSON and stdout: `graph-report.json` and `stdout.json`, both SHA-256 `5db9c3d3fea516916bc05d348e23c32597f66c7461abedfb0756ac2564076f9a`.
- Exact argv and cwd: `command.json` (SHA-256 `56b5b945b14eac5e2f45ee0efdf12f98927a045e8a7ec6b4f9a1af4e781fe2b2`); exit status 0; stderr empty.
- Executed prototype: `helper_topology_graph.py` (SHA-256 `10da5a86a83b01d19c758d4e82f7ec4ffe124f05297276bf56361d9e2342d38e`).
- Input manifest and complete graph are in `graph-report.json`; its manifest includes each input path, size, and SHA-256.
- Corrected slice metrics: `graph-corrected-metrics.json` (SHA-256 `395d2dead115c4dea26881cf3f2f88d397d2964dd2e256ace492a722106c757c`).

The first full JSON run labeled a test located directly under `tests/<layer>/` as a separate slice named after the test filename. I retained that exact output and corrected the slice metrics from the saved consumer paths using `<layer>` for a layer-root test and `<layer>/<directory>` for nested tests. The correction did not reread source files or rerun the graph. The raw report remains the complete source evidence; use the corrected-metrics artifact for slice totals.

No production source, test, configuration, baseline, or expiry files changed. No native SOTA wave, pytest, or numerical computation was run.


## Canonical location and source-freeze reconciliation

This canonical copy was placed under the product documentation handoff tree. The earlier receipt remains unchanged at /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/LOCAL/dx0-native/helper-topology-prototype-executed-20261010.md (SHA-256 bf9b96d05a1369a07c5c8b9d7841dc2f9b639e5a83df4e3851e70bf311d66b76). Its raw evidence remains unchanged at /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/LOCAL/raw/helper-topology-prototype-20261010/. The files beside this canonical note are byte copies in ../raw/helper-topology-prototype-20261010-original-location/; every copied file's SHA-256 and byte length were compared with its original after copying and matched.

The actual graph invocation was run from /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos with argv: python3 LOCAL/raw/helper-topology-prototype-20261010/helper_topology_graph.py --product-root policy-engine --output-json LOCAL/raw/helper-topology-prototype-20261010/graph-report.json. The wrapper redirected the complete stdout to stdout.json, stderr to stderr.txt, recorded exit status 0, and hashed the outputs. The command.json file preserves the argv and original cwd; the graph report's stdout and report JSON are identical (SHA-256 5db9c3d3fea516916bc05d348e23c32597f66c7461abedfb0756ac2564076f9a).

The run metadata claims HEAD=9194 only because that identity was supplied in the task. I did not query Git, so the commit/tree and source-freeze identity were not independently established. The actual input denominator is the report's 2,952-entry unique manifest: all 2,949 Python files enumerated under policy-engine/tests/, plus architecture/tests/ratchets.toml, architecture/baselines/repository_best_in_class_last_mile/test_helper_topology.json, and tools/quality/testing/report_test_ratchets.py. Their controlling-input hashes are:

- Ratchet TOML: b3660f2c663ad383fcb728c7b2560793957071c065a26d3ad2af7c9f656cb2c6.
- Baseline JSON: d3725f4bc510655204a00202be9081ea6851d017b9d986c3e6af31af3b17fee0.
- Reporter source: 800609f4f72be54392390ee2929a67621f9a104facc3d9c715d8274d93ce2f2b.

Slice reconciliation: the original graph-report.json is preserved byte-for-byte, including its first-pass slice labels. Its initial slice annotations incorrectly treated a test file directly under tests/<layer>/ as a separate slice. graph-corrected-metrics.json derives slice labels from the retained consumer paths (<layer> for a layer-root test, <layer>/<directory> for nested tests), without rerunning the source graph. Under that correction, the full graph has 59 test slices, with 16 multi-slice and 7 single-slice helper modules. The initial report's semantic_graph_metrics slice counts are superseded by that derived metrics file; neither count result establishes a ratified topology policy, native-green result, source freeze, or P41 provenance.

Canonical byte-copy readback:
- SHA256SUMS.txt: 899 bytes, SHA-256 b4d6af595520fc379719eeb878cfc236578a684d3d8d6c6ad1cc9051c96dcfdd (original and canonical copy match).
- command.json: 462 bytes, SHA-256 56b5b945b14eac5e2f45ee0efdf12f98927a045e8a7ec6b4f9a1af4e781fe2b2 (original and canonical copy match).
- exit-code.txt: 2 bytes, SHA-256 9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa (original and canonical copy match).
- graph-corrected-metrics.json: 15506 bytes, SHA-256 395d2dead115c4dea26881cf3f2f88d397d2964dd2e256ace492a722106c757c (original and canonical copy match).
- graph-report.json: 8998759 bytes, SHA-256 5db9c3d3fea516916bc05d348e23c32597f66c7461abedfb0756ac2564076f9a (original and canonical copy match).
- helper_topology_graph.py: 19196 bytes, SHA-256 10da5a86a83b01d19c758d4e82f7ec4ffe124f05297276bf56361d9e2342d38e (original and canonical copy match).
- stderr.txt: 0 bytes, SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 (original and canonical copy match).
- stdout.json: 8998759 bytes, SHA-256 5db9c3d3fea516916bc05d348e23c32597f66c7461abedfb0756ac2564076f9a (original and canonical copy match).
