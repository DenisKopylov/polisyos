# Neural warm checkpoint migration and operation

This recipe covers the internal `NeuralSearchStrategy` CPU GP state format.
New checkpoints declare `neural_warm_corpus.v1` and
`single_task_gp.cpu.refit_each_ask.v1`. The reader rejects old count-only warm
checkpoints because a count cannot reconstruct the measured inputs. Keep the
original checkpoint and history artifacts unchanged; there is no automatic
conversion or in-place rewrite.

## Rebuild a count-only checkpoint

1. Record the old checkpoint's full artifact reference and preserve its bytes.
   Locate the original persisted evaluations, candidate artifacts and benchmark
   evaluations. If those inputs are unavailable, stop warm migration. A fresh
   cold search is available, but is a new run rather than an equivalent resume.
2. Obtain the target owner's explicit `RunFingerprint` and complete technical
   `NumericTransferBasis` through the existing transfer manager. Use the same
   search space and intended `NeuralSearchConfig`. Do not derive a target basis
   from the first warm row or manufacture missing data, evaluator, split,
   metric, unit, direction or owner identifiers.
3. Configure the existing `WarmStartBridge` against that manager. Obtain the
   basis with `target_basis(fingerprint)` and the rows with
   `load_warm_start(fingerprint)`. Construct the strategy with that basis as
   `numerical_basis` and `bridge.admit_warm_start` as `warm_start_admission`,
   then call `warm_start(rows)`. Inspect both admission reports; rejected rows
   must not be counted as reconstructed measurements.
4. Call `get_state()`, serialize with the existing `StrategyState.to_artifact()`
   and persist through the configured CAS. Retain the full returned artifact
   reference and the original input references. This is a new checkpoint after
   explicit re-admission; it does not recover an absent legacy RNG position or
   establish next-proposal equivalence with the old count-only state.

## Restore a supported checkpoint

Configure a fresh strategy with the same space, non-seed configuration,
technical basis and admission reader. Read the exact checkpoint artifact,
decode it with `StrategyState.from_artifact()` and call `set_state()` before
requesting a proposal. The supported state carries the seed, Python RNG and
Sobol state, complete warm evaluation DTOs and references, corpus digest,
configuration and exact Torch, BoTorch and GPyTorch versions. CPU and
`torch.float64` are the supported numerical profile.

Restore re-resolves the original warm content before changing live state.
Subsequent training repeats admission. Missing or altered content, malformed
state, unsupported model bytes, mismatched basis, backend or configuration
cause an explicit refusal. Keep the refused checkpoint and the deciding error;
repair the actual configured input or rebuild from genuine history. Do not
edit the checkpoint's version fields, digest, refs or basis to make it pass.
The existing `ensemble` setting has no supported checkpoint profile here.

`set_state()` performs no model fit. Once the effective corpus reaches
`n_initial`, the existing CPU `SingleTaskGP` refits on each ask and uses the
minimized scalar convention. Below that threshold, the proposal follows the
supported Sobol profile. A Sobol-only check does not verify GP continuation.
If native fitting fails, the strategy's existing random fallback can run;
record that fallback rather than treating it as an equivalent GP proposal.

## Rollout and rollback

Deploy the supported reader and configured admission port together before
writing new warm checkpoints. Keep a full checkpoint reference and the
backend/configuration profile with the run record. An older reader is not a
supported consumer of the new state. A rollback must retain the new bytes and
use a separately supported old run or a fresh cold run; do not down-convert the
new state into a count-only checkpoint.

The bounded native evidence is recorded in
[`transfer-neural-state.json`](../research/e02-cloud-test-plan/implementation-handoffs/D/continuation/transfer-neural-state.json).
It includes fresh restore, original CAS mutation refusal, malformed RNG atomic
refusal and a real CPU GP continuation oracle. It establishes technical
content and numerical consistency for that profile. Institutional reuse
authority, a scientific history issuer, cross-version equivalence and an
empirical optimization-quality benefit remain outside this migration claim.
