# Onboarding: Domain / Policy Reader

Related explanation: [Trinity](../../explanation/trinity.md),
[Governance Model](../../explanation/governance-model.md),
[Data Fabric](../../explanation/data-fabric.md).

## Understand First

- what `ProblemFrame`, `PolicySpec`, and `ModelSpec` each mean;
- how evidence, lineage, and governance gates constrain decisions;
- where runtime/control-plane surfaces expose runs, artifacts, and decision
  validity without requiring source-code deep dives.

## Safely Ignore at First

- frontend build internals and bundle tooling;
- low-level Python packaging details and optional extras that are not needed for
  reading artifacts;
- signing/SBOM internals unless your review scope explicitly touches them.

## Commands and Docs to Use

Minimal local setup:

```bash
cd policy-engine
python3 -m tools.cli workspace bootstrap --skip-frontend --skip-playwright
```

Recommended docs path:

- [Getting Started](../../tutorials/getting-started.md)
- [Use Control Plane](../use-control-plane.md)
- [Debug Failed Run](../debug-failed-run.md)
- [Runs API](../../reference/api/runs.md)
- [Operations Runbooks](../../runbooks/index.md)

## First Productive Task

Take one completed run and answer:

- what policy question it attempted to solve;
- which evidence and data snapshot fed it;
- which governance signals allowed or blocked the outcome;
- whether the resulting decision artifact is actionable or incomplete.

Use runtime/control-plane endpoints and docs first; only open source code if the
artifact surface is insufficient.
