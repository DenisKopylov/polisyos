# Onboarding: Backend Engineer

Related reference: [IR](../../reference/ir/index.md),
[Fabric](../../reference/fabric/index.md),
[Scientist](../../reference/scientist/index.md),
[Foundry](../../reference/foundry/index.md).

## Understand First

- canonical product root is `policy-engine/`;
- the contributor path is `bootstrap -> doctor -> verify`;
- how contracts, runtime routes, and generated artifacts relate to each other;
- which subsystem you are actually touching before you edit it.

## Safely Ignore at First

- non-owning frontend route details unless your change crosses the API boundary;
- full benchmark universe beyond the suite relevant to your area;
- long-tail optional surfaces until your task needs them.

## Commands and Docs to Use

Canonical setup:

```bash
cd policy-engine
python3 -m tools.cli workspace bootstrap
python3 -m tools.cli workspace doctor
python3 -m tools.cli workspace verify --backend-only
```

High-signal docs:

- [Installation](../install.md)
- [Manage Schemas](../manage-schemas.md)
- [Deploy Runtime](../deploy-runtime.md)
- [Ownership](../../reference/ownership.md)
- [Operations Reference](../../reference/operations/index.md)

## First Productive Task

Choose one bounded backend task:

- update a contract-backed endpoint and regenerate the affected artifacts;
- fix a failing backend gate caught by
  `python3 -m tools.cli workspace verify --backend-only`;
- trace one failed run from `job_id` to `run_id` to artifact lineage and patch
  the broken service path.

The goal is to finish one change that exercises contracts, tests, and docs
together.
