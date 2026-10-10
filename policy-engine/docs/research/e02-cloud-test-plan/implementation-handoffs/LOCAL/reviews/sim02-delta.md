# SIM02 delta review

Review scope: the dirty SIM02 delta on base `077a572ff5880b3f50a85d3e3db6a232d277659a` (tree `2895b6c7597215b714275cb4ba83a504724dc89c`). At review readback, `HEAD` is still that base; the SIM02 source, tests, README, and release fragment are uncommitted. This note reviews the current working-tree bytes, not a later commit.

## Finding and disposition

The assignment-composition defect is one B20/P40 class: a simultaneous write must either be the same typed value or be refused, regardless of atom order. My first probe found a deeper scalar case in the shared resolver: Python equality treated `True` and `1` as identical, and the real program-parameter projection retained whichever type arrived first. The author widened the canonical equality function to compare JSON/Python value types recursively, added bool/int, int/float, and nested controls in both orders, and replaced the stale program-graph last-wins expectation with a refusal test plus a compatible real positive. This is the same class one level deeper, not a new class; no per-adapter patch is indicated.

The property-removal probe still distinguishes behavior from markers. With `_resolve_assignment_writes` replaced in-process by a last-write-wins implementation while the source error marker remains, the conflicting coupled request reaches the producer. With the current resolver, type-distinct program overrides and both parent/descendant path orders refuse. These probes are retained under the ignored `LOCAL/raw/sim02-review-current/independent-rerun/` directory.

The old artifact-backed program-graph test failed before reaching the graph because its fixture assigned `apply_subsidy.rate` both `0.1` and `0.2`. That was a stale expectation of last-wins behavior, not evidence that the new refusal was wrong. The revised suite now tests that conflict before graph execution and separately executes the real artifact-backed program graph with compatible `0.1` writes; the latter produces four state-delta-backed points and verifies the receipt.

## Runtime evidence and limits

The selected-engine preflight runs before any runner. The shared resolver is used by NCM interventions, coupled parameters, nested system-dynamics state/direct writes, program-node parameters, and method-registry state/direct writes. The focused tests exercise missing, malformed, and non-finite outcomes; explicit zero; order-independent compatible writes; conflict refusal; short-prefix coverage without terminal fill; and multistep scalar refusal. An independent NumPy stock-flow request with horizon step `2` produced steps `[0, 2, 4]` and matched `dt=2`; an explicit `dt=1` remained `not_established`. My actual system-dynamics adapter probe also refused a state-root/array-leaf collision. The coupled multistep scalar probe refused `admitted_count` instead of reusing the run-level value at every horizon point.

The real JAX coupled producer remains **UNRUN**, as required by this review slot. The coupled boundary tests patch its output and establish adapter projection behavior, not native producer execution. Keep that as a bounded `verification_missing` limitation; do not promote it to a native coupled-runtime pass. Time alignment is also only numeric parameter-to-step agreement: the README correctly states that it does not prove the consumed World Model Record's time alignment or authority. The prefix-overlap path passed a direct runtime probe but does not have a dedicated checked-in prefix-specific case; this is a test-coverage note within the same assignment-composition class, not a second defect.

## Verification

Independent rerun (numerical thread counts set to one):

```text
.venv/bin/python -m pytest -o addopts= -q \
  tests/unit/remediation/test_sim_02.py \
  tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_program_graph_plan_refuses_conflicting_shared_slot_before_execution \
  tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_program_graph_plan_loops_real_shared_state_executor
52 passed, 2 warnings in 31.97s
```

The two warnings are existing Python 3.14 Torch/JIT deprecations. `git diff --check` passed for the three reviewed source/test files. Full outputs: `LOCAL/raw/sim02-review-current/independent-rerun/focused.log` (SHA-256 `ed7b8ed1ebe3570deba45c2a3e96afba08f90bb7a5b6cbba32a8b514d6c625e8`), `property-probes.log` (`78ce85a3782a14d39de491521cfa9c3209c4a0f4794f2c24f6acc83e78824d40`), and `temporal-prefix-probes.log` (`4a535f10edc1a9445ce86bb81444daa156088b0548c17f46b38bd488aa699818`). The complete author run manifest is in `LOCAL/raw/sim02-review-current/type-sensitivity-green-attempt3/metadata.json`; its five path hashes match the live files.

Current reviewed path identities:

| Path | Current SHA-256 | Base Git blob at `077a572f` |
|---|---|---|
| `policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py` | `6e4dfa6ea2104bb0140d5d047f503b06525e1dc017b7495a9b4c150c3b8d895b` | `c8c933ee8c1ea7b8ae6e7f60de0d29e8005e672a` |
| `policy-engine/tests/unit/remediation/test_sim_02.py` | `c3968bd01205165bd7684da10d8e3ab53046bd301b4b52e38e674429f6d8fb01` | `31f830bd35eb5211771f712144a48a0af7d3ee47` |
| `policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py` | `ce7243f85ff404d45a26a873fdcafb89724dc14730c475edaee441dcb25b857c` | `9504676c5501e8a8e8909fac04c5b567c918b5ba` |
| `policy-engine/src/polisyos/runtime/quality/README.md` | `27e44b85f3d3f99b2995ca26f544fc00254d067ee494e91605bacffef3effd43` | not part of this review's implementation base census |
| `policy-engine/release-fragments/unreleased/2026-10-09-e02-sim02-adapter-semantics.toml` | `f3458a06ece3555bc4de6f9ed8f288926ae4a8ac38ab9e815caf9b66b97124ba` | added in the working-tree delta |

No later SIM02 commit was present at review readback; root must confirm the eventual committed path identity before treating this review as attached to a frozen commit.

## Commit readback confirmation

After the review above, I independently read the five reviewed file blobs from commit `24f3b72dd6eaa77cb7493d0880fe181e79181d75` (tree `421ee2bc4f24083777516c414975a7f899f91648`, parent `077a572ff5880b3f50a85d3e3db6a232d277659a`). Each committed blob's SHA-256 matches the reviewed bytes above; this supersedes the preceding timing note that the commit was not yet present. No tests or source changes were made for this confirmation.

| Path | Commit blob | Committed SHA-256 | Review match |
|---|---|---|---|
| `policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py` | `a6e5a9b8db44dabbf0cfc62b95e6a3453647cdc5` | `6e4dfa6ea2104bb0140d5d047f503b06525e1dc017b7495a9b4c150c3b8d895b` | yes |
| `policy-engine/tests/unit/remediation/test_sim_02.py` | `af048e3292accfe1e9f872428c60b4b0f12ab997` | `c3968bd01205165bd7684da10d8e3ab53046bd301b4b52e38e674429f6d8fb01` | yes |
| `policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py` | `892d79c1206a0d33c82792a1a6faf575d1b97cb8` | `ce7243f85ff404d45a26a873fdcafb89724dc14730c475edaee441dcb25b857c` | yes |
| `policy-engine/src/polisyos/runtime/quality/README.md` | `4adfde69a6e93f5eeb08aaf54c006e8f92ee3ffa` | `27e44b85f3d3f99b2995ca26f544fc00254d067ee494e91605bacffef3effd43` | yes |
| `policy-engine/release-fragments/unreleased/2026-10-09-e02-sim02-adapter-semantics.toml` | `09c408b08546b844518a373668e6e4729df6f2fe` | `f3458a06ece3555bc4de6f9ed8f288926ae4a8ac38ab9e815caf9b66b97124ba` | yes |

This confirms the SIM02 review is attached to those committed bytes. It does not assert completion of the repository-wide freeze/backend wave or acceptance of the broader G decision.
