# Runtime Reference

Owner: `@runtime-owners`
Source of truth: `policy-engine/src/polisyos/runtime/http/app.py`, `policy-engine/src/polisyos/runtime/http/routes/`, `policy-engine/src/polisyos/runtime/http/services/`, `policy-engine/schemas/runtime_api_v1.openapi.json`, and the linked runtime references
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`

This section explains how the PolicyOS runtime assembles requests, reads stored
run and artifact state, admits mutations, and projects results to clients. It is
an implementation guide. The [REST API reference](../api/index.md) and committed
OpenAPI document remain the contract sources for HTTP operations and schemas.

## Start here

- [Current request lifecycle](current-request-lifecycle.md) traces app
  composition, identity and tenant checks, read projections, durable writes,
  candidate boundaries, custody, and audit records.
- [REST API reference](../api/index.md) links endpoint-specific pages for runs,
  control, artifacts, identity, errors, and compatibility.
- `policy-engine/src/polisyos/runtime/http/README.md`
  maps the app factory, middleware, dependencies, services, and OpenAPI inputs.
- `policy-engine/src/polisyos/runtime/http/routes/README.md`
  and `policy-engine/src/polisyos/runtime/http/services/README.md`
  map the route and application-logic owners.

## Choose a reference by task

| If you need to understand… | Read |
| --- | --- |
| Identity, permissions, tenant scope, or request admission | [Auth and tenant model](../api/auth-tenant-model.md), [current request lifecycle](current-request-lifecycle.md) |
| Run listing, details, replay, comparison, and live views | [Runs API](../api/runs.md), [deterministic replay](deterministic-replay.md) |
| Run launch, durable jobs, acquisition, or control-plane writes | [Control Plane API](../api/control.md), [runtime request lifecycle](current-request-lifecycle.md) |
| Artifact inspection, selected profiles, or CAS storage | [Artifact Inspection API](../api/artifacts.md), [CAS and storage](../operations/cas-storage.md) |
| Error bodies, API compatibility, or client migration | [Error semantics](../api/error-semantics.md), [versioning](../api/versioning.md), [migration guide](../api/migration-guide.md) |
| Quality gates, production eligibility, and approval | [Quality scorecard](quality-scorecard.md), [production-quality approval](production-quality-approval.md), [production data quality](production-data-quality.md) |
| Calibration, human review, or counterfactual diagnostics | [Calibration ledger](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/docs/reference/runtime/calibration-ledger.md), [human-review calibration](human-review-calibration.md), [counterfactual layer](counterfactual-layer.md) |
| Cost, degradation, and bounded execution | [Cost and degradation telemetry](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/docs/reference/runtime/cost-degradation-telemetry.md), [run-cost enforcement](run-cost-enforcement-gate.md), [run-cost proportionality](run-cost-proportionality-ledger.md) |
| Public document rendering, privacy, and operational readiness | [Bureaucratic rendering](bureaucratic-rendering.md), [privacy compliance evidence](privacy-compliance-evidence.md), [production resilience](production-resilience-matrix.md) |

## Runtime topic references

### Evidence, analysis, and output

- [Policy diff](policy-diff.md)
- [Quantity values](quantity-values.md)
- [Provider and model quality](provider-model-quality.md)
- [Best-in-class benchmarking](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/docs/reference/runtime/best-in-class-benchmarking.md)

### Readiness and production operation

- [Production quality maturity](production-quality-maturity.md)
- [Production canary matrix](production-canary-matrix.md)
- [Production resilience matrix](production-resilience-matrix.md)
- [Production data quality](production-data-quality.md)
- [Production quality approval](production-quality-approval.md)
- [Runtime quality scorecard](quality-scorecard.md)

### Governance and cost

- [Calibration ledger](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/docs/reference/runtime/calibration-ledger.md)
- [Human-review calibration](human-review-calibration.md)
- [Cost and degradation telemetry](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/docs/reference/runtime/cost-degradation-telemetry.md)
- [Run-cost enforcement gate](run-cost-enforcement-gate.md)
- [Run-cost proportionality ledger](run-cost-proportionality-ledger.md)
- [Privacy compliance evidence](privacy-compliance-evidence.md)

### Runtime behavior

- [Deterministic replay](deterministic-replay.md)
- [Counterfactual layer](counterfactual-layer.md)
- [Bureaucratic rendering](bureaucratic-rendering.md)

## Source owners

- `policy-engine/src/polisyos/runtime/http/app.py` assembles
  the FastAPI app, middleware, router mounts, and startup/shutdown lifecycle.
- `policy-engine/src/polisyos/runtime/http/dependencies.py`
  builds request context and owns shared run/artifact tenant checks and read
  audit helpers.
- `policy-engine/src/polisyos/runtime/http/services/README.md`
  owns application services, durable control orchestration, and read-side
  projections.
- `policy-engine/src/polisyos/runtime/README.md` maps the runtime
  quality owners, including candidate-to-authority checks and replay services.

## Reading boundary

The behavior described here is based on code inspection. No runtime API server,
deployment identity provider, OPA service, external producer, or database
concurrency scenario is exercised by this reference. Endpoint schemas and
contract snapshots are maintained separately; schema-hidden live run streams
and route behavior should be checked against the route owners.

Source presence and route availability are not proof of an end-to-end causal
policy capability or a publishable recommendation. Such a claim needs the
producer, typed artifact/event, orchestration bridge, consumer, verification,
audit/public surface, and semantic test to be demonstrated together. Keep
candidate output candidate-only; an unknown candidate scope may remain only as
a typed limitation where that path permits it. Protected actions, custody
facts, and published claims fail closed rather than silently replacing unknown
scope with a concrete value.

Validation status: Source and test-reference inspection only for this
documentation update; no runtime, provider, or end-to-end scenario was run.
E02 remains unfinished at this source pin.

- Last updated: 2026-10-14
