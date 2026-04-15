# Foundry Observability and Reproducibility

Foundry is no longer a black box at method execution time. WS-10 adds
operator-facing hooks so a run can answer four practical questions without
reading source:

1. What method/backend actually ran?
2. How much time and estimated cost did it consume?
3. Was the result degraded or replayable only within tolerances?
4. Which methods were applicable on this runtime?

## Runtime Artifacts

Every backend `MethodResult` now carries `backend_runtime_fingerprint` in
`artifacts`. The dispatch layer adds:

- `dispatch_trace`: requested backend, selected backend, attempts, selection
  reason, predicted latency, and degradation status.
- `cost_attribution`: wall time, compile time, CPU time, estimated USD cost,
  determinism tier, and seed.

These artifacts are designed for artifact storage, audit surfaces, and
OpenTelemetry export. The dispatch layer also emits
`foundry.method.dispatch` spans with method/backend attributes.

## Determinism Contract

Foundry distinguishes declared method semantics from observed runtime posture.
Catalog snapshots publish the effective determinism tier plus the runtime
posture used to derive it.

| Tier | Replay semantics |
|------|------------------|
| `strict_cpu` | Bit-exact on the same CPU ISA |
| `library_deterministic` | Exact within the same CPU/library stack |
| `best_effort_gpu` | Near-deterministic on the same GPU family |
| `statistical` | Seed-stable only up to interval/envelope semantics |
| `nondeterministic` | Best effort only |

Capability rows also include a `tolerance_budget` so x86 vs ARM acceptance runs
can use explicit tolerances instead of relying on undocumented assumptions.

## Capability Matrix

`build_method_catalog_snapshot()` persists the machine-readable capability
matrix that planners and operators can query. Each row now includes:

- `runtime_posture`
- `declared_determinism_tier`
- `runtime_determinism_tier`
- `determinism_tier` (effective / conservative)
- `replay_semantics`
- `tolerance_budget`
- `truthfulness_tier`

This keeps backend availability claims aligned with installed runtime stacks.

## Release Acceptance Evidence

The Foundry release gate now treats bundle replay as a first-class release
artifact, not a manual checklist item. The gate runs the same D5
release-acceptance roundtrip used by the production bundle builder and uploads
`foundry-release-acceptance.xml` beside the capability matrix and operator
evidence. That JUnit artifact proves the assembled bundle can still:

- verify release manifest hashes;
- materialize a bundle-backed `GlobalState`;
- compile the acceptance contract into an execution plan;
- execute the simulation step;
- pass governance postflight checks;
- replay and compare stable simulation/metrics payloads.

## Advisor and CLI

The `polisyos-foundry` CLI now exposes operator workflows directly:

```bash
polisyos-foundry capabilities --runnable-only --json
polisyos-foundry evidence --json
polisyos-foundry release-acceptance --manifest-path bundle/release_manifest.json --runtime-bundle-dir bundle/runtime --method-contract-bundle-dir bundle/contracts --store-root .foundry-release-cas --json
polisyos-foundry advisor --family causal.treatment_effects --required-modality cross-section --n-obs 5000 --runtime-budget-ms 50 --json
```

Use `capabilities` when you need the full machine-readable inventory. Use
`evidence` when you need an operator-facing summary of runnable vs blocked
methods, replay contracts, and the top disabled reasons that explain degraded
applicability on the current runtime. Use `release-acceptance` when you need
the bundle-backed acceptance roundtrip report that proves compile, execute,
governance, and replay verification still work together on a real release
bundle. Use
`advisor` when you need a ranked answer to "which methods apply to my problem?"
with backend, fidelity, determinism, and truthfulness metadata.

## Recommended Acceptance Loop

For release or platform debugging:

1. Persist a catalog snapshot artifact.
2. Persist the operator-evidence JSON next to the capability matrix so release
   reviews have one compact applicability/replay summary.
3. Run `polisyos-foundry release-acceptance --json` against the assembled bundle
   and persist the report alongside capability evidence. CI also publishes
   `foundry-release-acceptance.xml` from the bundle-backed acceptance test.
4. Run targeted goldens on the relevant backend/runtime family.
5. Inspect `dispatch_trace`, `cost_attribution`, and
   `backend_runtime_fingerprint` for degraded or expensive paths.
6. Compare replay outputs using the published `tolerance_budget`, not ad hoc
   absolute tolerances.

This is the intended operator contract for Foundry as a production
computational system.
