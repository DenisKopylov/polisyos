# P41 architecture guardrail comparison

**Decision: `not_established`; BLOCK the inherited-red exemption for this bounded gate.** The exact architecture guardrail output reproduces at base c40, but the changed source paths are not disjoint from its complete deciding inputs. This does not prove that the candidate source change caused every reproduced finding.

## Replay and outputs

The base replay ran on attached branch `codex/e02-A-guardrails-base`, source `c40d4acae1ce58b597267255026d9356565828fd`, with the exact child command `.venv/bin/polisyos-tools architecture guardrails check` from `policy-engine/`. It exited 1 in 260.266 seconds under CPython 3.14.3. The environment used PATH `uv` 0.10.6 and Corepack pnpm 10.33.2; offline frozen uv and pnpm setup completed before the gate replay.

The base raw output is `/Users/deniskopylov/.codex/worktrees/e02-a-guardrails-base/polisyos/policy-engine/_build/e02-A-guardrails-base/n5-binding/architecture.txt` (1,991 lines, 115,262 bytes, SHA-256 `e4cd720fca791f7471d387368e2b2d605dedc6813229ebb6066df8581bfbb8d3`). The candidate raw output is `/Users/deniskopylov/.codex/worktrees/e02-a-custody/polisyos/policy-engine/_build/e02-A-custody/n5-binding/raw/architecture-candidate.txt` (1,991 lines, 115,246 bytes, SHA-256 `cf18007dc62717fb7418be445b544ab6c8852450da687ac2890a36e95d216057`), produced for candidate source `e7d034756cb11522c65f602e021fccef5bc6245c`.

The comparison replaces only the exact base and candidate worktree-root byte strings with `<WORKTREE>`; each occurs twice. The normalized streams are both 115,148 bytes and byte-identical. No warning or error lines were removed. Each raw stream has 151 deep-import findings and two generated-output mismatches: runtime OpenAPI and trust posture.

## Complete source denominators and P41 finding

The comparison script reads the c40 source tree using `git ls-tree` and `git cat-file --batch`, not the current worktree. The complete `policy-engine/src/**/*.py` blob set contains 2,697 files. Mirroring the guardrail's module/root mapping leaves 2,696 modules in the deep-import AST denominator. The c40→e7 tree delta is nine paths: seven verification-baseline documents/logs, `src/polisyos/runtime/quality/generation_cycle.py`, and `tests/unit/remediation/test_cyc_02.py`. Exactly one changed path intersects the deep-import module denominator: `polisyos.runtime.quality.generation_cycle`. Its AST import nodes are unchanged across c40 and e7, but P41 requires a zero path intersection, which is not met.

The trust posture source walker also reads all 2,697 Python blobs; 145 contain `authoritative_for` or `may_not_use_for` and enter its candidate source set. The changed `generation_cycle.py` is one of those 145, and its blob digest changes from c40 to e7. This is an actual source-set overlap. The seven changed documents and the test file are outside these `src/**/*.py` denominators.

The generated-artifact manifest read from c40 declares four required freshness families with six outputs. The red rows are the runtime OpenAPI snapshot and trust-claim posture register. Treat the red gate as `not_established` for provenance; do not record the whole reproduced red as inherited based on the base replay alone.

## Reproduction artifacts

`p41-compare_p41_architecture.py` locates the repository with `git -C <script-parent> rev-parse --show-toplevel`, accepts optional `--base-log` and `--candidate-log` paths, reads source counts and the generated-artifact manifest from the pinned c40 Git blobs, and compares the retained raw logs. The complete moderate output is `p41-comparison.txt`. Script formatting and lint both passed with Ruff 0.14.10.

From the candidate repository root, reproduce only the comparison (the 260-second architecture gate was not rerun during this receipt repair):

```sh
policy-engine/.venv/bin/python policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/A/p41-compare_p41_architecture.py > policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/A/p41-comparison.txt
```

To replay the original deciding gate from the c40 base worktree:

```sh
cd policy-engine && .venv/bin/polisyos-tools architecture guardrails check
```
