# Onboarding: Platform / Ops Engineer

Related reference: [Operations Reference](../../reference/operations/index.md).
Related runbooks: [Runbooks](../../runbooks/index.md).

## Understand First

- canonical workspace commands and supported baselines;
- runtime/control-plane deployment surfaces and optional env-backed surfaces;
- where dashboards, alerts, traces, logs, and runbooks connect;
- which retained artifacts can be restored versus merely regenerated.

## Safely Ignore at First

- deep algorithmic details of every Foundry or Lex method;
- long-tail tutorial material not tied to operator workflows;
- feature-level frontend polish outside operational pages.

## Commands and Docs to Use

Canonical operator path:

```bash
cd policy-engine
./scripts/bootstrap
./scripts/doctor --list-surfaces
./scripts/doctor --surface runtime-research-postgres --surface runtime-signing
./scripts/verify
```

Observability local stack:

```bash
cd policy-engine/ops
docker compose -f docker-compose.observability.yml up
```

Required docs:

- [Deploy Runtime](../deploy-runtime.md)
- [Use Control Plane](../use-control-plane.md)
- [SLO and Error Budget Policy](../../reference/operations/slo-error-budget.md)
- [Observability Topology](../../reference/operations/observability-topology.md)
- [Retention and Recovery Policy](../../reference/operations/retention-and-recovery.md)

## First Productive Task

Run a small operational drill end to end:

- bring up the observability stack;
- verify one trusted dashboard and one alert family owner;
- execute one restore or replay drill from the retention policy;
- document any missing signal, owner, or runbook step you hit.
