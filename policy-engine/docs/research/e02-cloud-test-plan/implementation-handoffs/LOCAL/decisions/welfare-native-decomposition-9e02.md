# Welfare implementation decomposition and B194 classifier integration

This is a source-readiness receipt for the Welfare decomposition in the `9e02a9f49c8b01026327a9f7c7e18711b13a96f2` task slice. It is not a final candidate freeze, a native numerical-wave receipt, or a G finding closure.

## Change boundary

The public `PropagateWelfareNode` and `WelfareSampleDomainError` identities remain in `propagate_welfare.py`; that facade forwards the existing evaluator and sample-draw seams. Context resolution, GE handling, covariance/joint rows, draw execution, report persistence, and node orchestration now live in adjacent `welfare_*.py` modules. The output schemas and scientific assumptions were not changed by the split.

Welfare no longer implements a separate exception graph walker. It delegates to `polisyos.foundry.uncertainty.evaluation_failures.classify_evaluation_failure`, passing the facade-owned `WelfareSampleDomainError` and `_WelfareNodeFailure` types. The shared bounded graph traversal distinguishes a shared cause/context DAG from a cycle, gives visible global access/validation/fatal errors precedence, and leaves truncated/cyclic or untyped failures unknown. Existing transient retry remains bounded to two attempts on the same sampled input; only the explicit Welfare sample-domain signal remains a candidate partial draw. This is the same B194 failure-scope class widened to one shared mechanism (P40).

## Source and output identities

All listed implementation modules are below the 1,000 nonblank-line ceiling; C901 at the repository default threshold passes across all nine Welfare source modules.

| File | Nonblank lines | SHA-256 |
|---|---:|---|
| `src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py` | 64 | `993a434317e54b6db23626ba56e60e0973312fe960e57cc2c2cc76cdae981c7f` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_context.py` | 764 | `67b8d609fe101e9b13756b651af03bb0740940e7415a6913b3f30c11581b116a` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_covariance.py` | 991 | `c5cb907b8312b52f0504cbacf3e2a38e147909a0acf8db6d04ac741607bc2d65` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_draws.py` | 692 | `99d2adc8509354890a92de6380e23b973966f141f5a2b7a68f3fa2e8f2f09d38` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_ge.py` | 715 | `ad740b6579a91b76ff005b3c2bbecd7a1f84d4827298627ec08f5aae84f41cea` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_node.py` | 473 | `b321051e25133161b0d504366cbdc0cb55391778430b1a685e1a46329ef698bf` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_propagation.py` | 750 | `3633130f341dea915e1876ca1e148c7e26cd0ab34811d4fed870c240686a24bb` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_reports.py` | 644 | `5040ee6a1192a88551ff6efc83944cb8b5e2f44fe508e9368a85ed11ac8d3807` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_types.py` | 319 | `80c7724be00d61bb2202d322b70d0bc2d525ce7d23328e9bf1bc0557af1a00a8` |

The shared classifier source is q1-owned: `src/polisyos/foundry/uncertainty/evaluation_failures.py`, SHA-256 `a371c4e8ad6ca37d3d94bb69fefad541c442fcec233c2a7305ea689fffca9050`.

The mirrored Welfare test file is `tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py`, SHA-256 `404e8d3217f581bfe2a6bf63b8a5c3d1a299f54cbf15c17647a9df9cf38d3280`. The E11 release fragment is `release-fragments/unreleased/2026-10-09-e02-e11-welfare-monte-carlo-truthfulness.toml`, SHA-256 `00466449ea0b367db7f3f5264e72c0fa3c4bce9691ada65f729fcef20cdac60f`; it now inventories the façade, helper modules, shared failure classifier, and mirrored test.

## Verification

The adapter test was added before changing the Welfare classifier. The initial run failed as intended: the local implementation returned `transient` when the shared classifier returned `unknown`. After delegation, the selector passed.

The post-change focused command was:

```text
.venv/bin/python -m pytest -vv --junitxml=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/s1-law-intakes/raw/welfare-adapter/welfare-draw-focused.xml -k 'partial_welfare_draws_retain_terminal_outcomes or retries_explicit_transient_on_same_draw or persistent_transient_is_bounded or requires_explicit_sample_domain_signal or does_not_launder_global_or_unknown_failures or failure_scope_uses_shared_foundry_classifier' tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py
```

Exit 0; JUnit reports **16 passed, 35 deselected, 0 failures, 0 errors, 0 skipped** on the existing product `.venv` (Python 3.14.3). Two unrelated `torch.jit.script` Python 3.14 deprecation warnings were emitted. Full stdout SHA-256 is `1d11637f9a40200f26518a25396294cdfa98dd922d13af9b45a55bd629de5ade`, stderr is empty (SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`), and JUnit SHA-256 is `63c36d35f41aa448761c53ecaacbae625376be44cef4cd3e9e0e9d1076a5c385`. The raw files are under `LOCAL/s1-law-intakes/raw/welfare-adapter/`.

The following checks completed with exit 0:

- Ruff on all Welfare modules, the mirrored Welfare test, and the shared classifier: `All checks passed!`.
- Ruff C901 on the nine Welfare implementation modules: `All checks passed!`.
- Ruff format check on those paths and the shared classifier: `11 files already formatted`.
- `compileall -q` on the same implementation and test paths.
- JSON parse of the updated final numerical command plan and TOML parse of the existing E11 release fragment.

The plan at `LOCAL/s1-law-intakes/final-numerical-command-plan.json` (SHA-256 `70a58d0c2c7d44d7be69f45ea7746ff0185d150b4a036a08566b7e82b1eade9e`) now includes the generic Monte Carlo exact-symmetric B194 witness: 100 fixed `y=x` draws, 50 failures/50 successes, `mc_min_valid_samples=10`, a fresh normative CAS consumer, and a separate global access-failure control. The plan records no measured time for that exact selector. No HMC, calibration fit, heavy numerical wave, or collection was run here.

## Remaining boundary

The final native HMC/MethodJob, calibrated Welfare fit, native response-basis, paired-row law, and complete S2/S3 wave remain pending the root-owned source freeze and native checker repair. These checks must be run under the frozen source/profile recorded in the command plan. A shared joint-axis ID, covariance matrix, matched marginals, or row pairing alone does not establish an external joint law; no scientific law, calibration, billing, or institutional fact is inferred here. No formal finding closure is claimed.

Suggested root-owned README paragraph: “`simulate/propagate_welfare.py` retains the registered `PropagateWelfareNode`, its sampled-domain error identity, and stable evaluator/sampler seams. Private context, GE, covariance, draw, propagation, report, and node orchestration helpers live in adjacent `welfare_*.py` modules; Welfare and generic Foundry Monte Carlo share the bounded evaluation-failure classifier.”
