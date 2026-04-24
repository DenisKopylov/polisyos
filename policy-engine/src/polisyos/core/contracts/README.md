# Contracts (`polisyos.core.contracts`)

`core.contracts` is the typed ABI layer of PolicyOS. It defines the shared refs, request/response
models, and provenance payloads that let `fabric`, `foundry`, `scientist`, `lex`, `runtime`, and
`scholar` talk to each other without ad hoc JSON shapes.

## Role in System

- **Depends on:** `core.artifacts` for CAS-backed `ArtifactRef` and `polisyos.ir.refs` for canonical analytics refs.
- **Used by:** runtime HTTP routes, control-plane orchestration, domain pipelines, and audit/provenance tooling.
- **Boundary function:** prevents each domain package from inventing its own incompatible payload schema.

## Key Concepts

- **Typed refs** - every artifact family uses explicit `kind` and `media_type` checks.
- **Runtime/control DTOs** - HTTP and orchestration payloads live here so routes stay thin.
- **Compatibility facades** - analytics refs that migrated into `polisyos.ir.refs` still have stable re-export paths here.
- **Provenance payloads** - shared entity/agent/activity records keep audit and lineage data consistent.
- **Execution planning** - `execution_plan.py` carries preflight, evaluator, and reproducibility artifacts.
- **Scientist artifacts** - scientist-specific refs include decision, checkpoint, sensitivity, stress, and calibration validation bundles.

## Public API

Main ref families:

- `fabric.py`, `foundry.py`, `scientist.py`, `scholar.py`
- `trinity.py`, `compiler.py`, `lex.py`, `execution_plan.py`
- `runtime.py`, `control.py`, `cursor.py`
- `provenance.py`
- compatibility facades: `backtest.py`, `causal.py`, `distributional.py`, `hte.py`, `uncertainty.py`

Notable current exports include `ExecutionPlanRef`, `PreflightReportRef`, `RunDetailsResponse`,
`DecisionValidityEnvelope`, `ProvenanceCoreRef`, and `CalibrationValidationBundleRef`.

## Current State

- Last updated: 2026-04-03
- The scientist contract family gained `CalibrationValidationBundleRef`.
- `core.contracts` still acts as the stable import surface for runtime/control payloads while analytics refs continue to be re-exported for compatibility.
