# Independent receipt-integrity review: runtime promotion reason precedence

## Verdict

**GO for a separate receipt commit, with a bounded-evidence qualification.** The protected receipt, source checkpoint, remote readback, selected-file hashes, and retained test outputs agree. The recorded focused run is a source-worktree run at `55ed8863a8cad50c8189dd9309f0a87e8761016b`; it is not evidence for the later current checkout, an installed profile, or the full 177-case set.

## Protected record and source binding

- Protected record: `LOCAL/runtime-promotion-reason-precedence.json`, SHA-256 `73fd7d857a67873e2a78b060891a5db47b67d226cb31315e5dc285ab1b4b8251`.
- Source checkpoint: commit `e038ab5701f59841a0b30229e8edfcd8e303b64c`, tree `a610b9e1c0b5a2f0a786ba8d4b5344b06d3c3053`, parent/slice base `28efd19763dee0a12d64e6794f6cc4b4c0829b04`. It changes one test file and records two expectation replacements in `tests/unit/runtime/quality/test_promotion_sequence.py`.
- The local checkpoint readback is `LOCAL/raw/runtime-promotion-test-source-checkpoint-20261011/readback.json` (`07aa23c8177ef7d2de26cfb6db0e043065f8fb089575142af593c3044836d948`); its remote readback is `.../remote-readback.json` (`058393eb858814c3cd3a69cd70afb494ed01f7bed6b58de115b91a154c756713`). Both bind the same commit, tree, parent, preimage `8175f936bc311b80a645681c3b2cf0ee1013ab2d4f66013841182611b725c1a0`, and candidate `eba17d969546fd412a7b9414cb764c740f81884012c7db26ce536fecc3a0f219`. The selected-footprint receipt (`.../selected-footprint.json`, `8078799f09a868597abdc8af1e0b4a17d14e4295c7af2f5ca0a86837b494d555`) names that same single path and candidate hash.
- At audit checkout `785944776c39722923c3a34d4ab7a3594dc03287`, the selected test file still hashes to the candidate. Other runtime-quality files and sibling tests are modified in the worktree; they postdate this captured run and were not verified by it.

## Run evidence and limits

The initial boundary run is retained at `LOCAL/raw/batched-blocking-focused-20261010/runtime-promotion-first-real-failure-boundary-20261011/`. Its command manifest hash is `9f9dacef1335a0500c66a15d4f75602c4022cf318232adb411dd056c3bd99f49`; stdout is `f3ba26950f1b53f5b969a7637e472f359bba76ced6af00808bc422008f86917b`, and JUnit is `d8d17c4889192d0ded4aa4a504855eac57e272488ddb782d55c54ed7888f8dd4`. It collected 177, passed 13, then failed on a stale reason expectation under `--maxfail=1`; 163 cases were not run. The receipt labels this correctly and does not present that attempt as a pass.

The bounded follow-up is recorded in the IR receipt and raw command directory `LOCAL/raw/batched-blocking-focused-20261010/promotion-two-current-refusals-and-ir-lag-routing-20261011/`. Command manifest SHA-256 is `b558b19452fe5cd33f4d5a70d3a3e48217ef7c2fba8de32bc864ce603a9d0fce`; stdout is `3e976b655a27bb74489b50c9202231ec5269243f3aab2c2598afa8110fc95043`, stderr is empty, and JUnit is `1e640013008df61d6746e875098188392874fea71a09c0e2fefe941e9f216a2a`. JUnit and the receipt reconcile to 48 passes: 2 promotion, 37 IR contract, and 9 discovery-reconciliation tests; no failures, errors, or skips. The command used the worktree `.venv/bin/python`, `PYTHONPATH=src:.`, and captured HEAD `55ed8863a8cad50c8189dd9309f0a87e8761016b`. Its recorded 6,160 input paths were stable before and after the run. This is focused source-tree evidence, not installed-wheel or full-suite evidence.

The bounded Ruff command is separately recorded at `LOCAL/raw/batched-blocking-focused-20261010/promotion-ir-archive-five-canonical-ruff-final-20261011/command.json` (SHA-256 `654454a9d12b06ceaa8b621298080f70a35508b91043881c015444ffb7e84232`). It ran at base `28efd19763dee0a12d64e6794f6cc4b4c0829b04`, over five targets and two configuration inputs, with zero diagnostics. It does not validate later worktree edits.

The receipt's disposition is bounded test-expectation alignment. `formal_closure_claimed` is `false`, `id_proposals` is empty, and the full 177-case rerun, native Linux suite, and repository suite are recorded as not run. No promotion or production-authority claim follows from these test results.

## Pattern pass

Relevant register rows are P29 (recomputed evidence), P38 (state which run and property are evidenced), and P41 (bind a result to its actual base and complete captured input set). The receipt keeps the initial failure, focused pass, source checkpoint, and later checkout distinct, avoiding a marker/exit-code-only claim or a full-suite implication.
