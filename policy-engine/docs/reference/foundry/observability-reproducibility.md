# Foundry Observability and Reproducibility

Foundry observability answers four operator questions without requiring source
inspection:

1. What method/backend actually ran?
2. What runtime/device posture was observed?
3. Was the result degraded or replayable only within tolerances?
4. Which methods were applicable on this runtime?

This page covers Phase 4 performance/concurrency/reproducibility and the
cross-cutting WS-10 documentation/observability surface from the Foundry plan.

Freshness: 2026-04-17
Owner: `@foundry-owners`
Source plan: `docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md`, D1-L3 section in `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/foundry/runtime/**`, `src/polisyos/foundry/methods/backends/**`, `src/polisyos/foundry/release_acceptance.py`, benchmark registry/help surfaces, and generated method snapshot inputs from `src/polisyos/foundry/methods/catalog_snapshot.py`

## Runtime Artifacts

Every backend `MethodResult` can carry `backend_runtime_fingerprint` in
`artifacts`. Dispatch and catalog evidence may include:

- `dispatch_trace`: requested backend, selected backend, attempts, selection
  reason, predicted latency, and degradation status.

- `cost_attribution`: wall time, compile time, CPU time, estimated cost,
  determinism tier, and seed.

- `runtime_posture`: observed backend, available packages, runtime stack, device
  family, replay semantics, and tolerance budget.

These artifacts are intended for CAS storage, audit surfaces, OpenTelemetry
export, and release reviews.

## Determinism Contract

Foundry distinguishes declared method metadata from observed runtime posture.
Capability rows should publish both so docs and planners do not overclaim
replayability.

| Tier                    | Replay semantics                                                                         |
| ----------------------- | ---------------------------------------------------------------------------------------- |
| `strict_cpu`            | Bit-exact on the same CPU ISA; cross-architecture runs use an explicit tolerance budget. |
| `library_deterministic` | Exact within the same CPU/library stack; cross-ISA uses the published tolerance budget.  |
| `best_effort_gpu`       | Near-deterministic on the same GPU family.                                               |
| `statistical`           | Seed-stable only up to interval or distributional semantics.                             |
| `nondeterministic`      | Best effort only.                                                                        |

The tolerance-budget implementation lives in
`polisyos.foundry.methods.backends.runtime_fingerprint` and is exercised by
`tests/unit/foundry/methods/backends/test_backend_determinism.py`.

## Capability Matrix

`build_method_catalog_snapshot()` and `build_method_capability_matrix()` are the
machine-readable inventory surfaces for planners and operators. Rows can include:

- `runtime_posture`
- `declared_determinism_tier`
- `runtime_determinism_tier`
- `determinism_tier`
- `replay_semantics`
- `tolerance_budget`
- `truthfulness_tier`

This keeps backend availability claims aligned with installed runtime stacks.

Regenerate the underlying machine-readable inputs with:

```bash
uv run python - <<'PY'
from polisyos.foundry.methods.catalog.snapshot import (
    build_method_capability_matrix,
    build_method_catalog_snapshot,
    build_method_operator_evidence,
)

snapshot = build_method_catalog_snapshot(run_id="docs")
print(snapshot.snapshot_id)
print(len(build_method_capability_matrix(snapshot, runnable_only=True)))
print(build_method_operator_evidence(snapshot, runnable_only=True)["replay_contracts"][0]["determinism_tier"])
PY
```

## CLI Workflows

```bash
uv run polisyos-foundry capabilities --runnable-only --json
uv run polisyos-foundry evidence --json
uv run polisyos-foundry advisor --family causal.treatment_effects --required-modality cross-section --n-obs 5000 --runtime-budget-ms 50 --json
```

Bundle-backed release acceptance is available when an assembled release bundle
exists:

```bash
uv run polisyos-foundry release-acceptance \
  --manifest-path bundle/release_manifest.json \
  --runtime-bundle-dir bundle/runtime \
  --method-contract-bundle-dir bundle/contracts \
  --store-root .foundry-release-cas \
  --json
```

The release-gate workflow is asserted by
`tests/unit/foundry/validation/test_release_gate.py`.

For machine-readable automation, prefer the Python regeneration path above.
Current CLI `--json` runs may include registry-bootstrap logs before the JSON
payload on stdout.

## Benchmark Command Boundary

The current benchmark command boundary for this reference set is:

```bash
uv run polisyos-tools benchmarks run-all --help
uv run pytest tests/unit/foundry/benchmarks/test_ws5_jax_perf.py -m benchmark --benchmark-only
uv run pytest tests/unit/foundry/benchmarks/test_ws5_jax_perf.py -m benchmark --benchmark-json=ws5-bench.json
```

`polisyos-tools benchmarks run-all --help` is the verified command entrypoint,
while the `test_ws5_jax_perf.py` benchmark file is the Foundry/JAX hot-path
anchor linked from this page and from [Run Benchmarks](../../how-to/run-benchmarks.md).

## Recommended Acceptance Loop

1. Persist a catalog snapshot artifact.
2. Persist operator-evidence JSON beside the capability matrix.
3. Run release acceptance against the assembled bundle when bundle artifacts are
   available.
4. Run targeted goldens on the relevant backend/runtime family.
5. Inspect `dispatch_trace`, `cost_attribution`, and
   `backend_runtime_fingerprint` for degraded or expensive paths.
6. Compare replay outputs using published `tolerance_budget`, not ad hoc
   tolerances.

## Numeric and JAX Evidence

Numeric/JAX claims in this documentation should point to one of these anchors:

- NaN guard model and runtime checks:
  `tests/unit/foundry/runtime/test_nan_guard_public.py`,
  `tests/unit/foundry/runtime/test_nan_guard.py`

- Numerical stability:
  `tests/unit/foundry/methods/backends/test_numerical_stability.py`

- Cross-backend consistency:
  `tests/unit/foundry/methods/test_cross_backend_consistency.py`

- Agent-sim JIT compatibility:
  `tests/unit/foundry/agent_sim/test_jit_compatibility.py`

- Performance benchmark ratchet:
  `tests/unit/foundry/benchmarks/test_ws5_jax_perf.py`

- Numeric policy note:
  `docs/reference/foundry/numeric-guardrails.md`

## Reference

::: polisyos.foundry.methods.backends.runtime_fingerprint

::: polisyos.foundry.runtime.fingerprint

::: polisyos.foundry.validation.release_acceptance

::: polisyos.foundry.methods.catalog.snapshot
