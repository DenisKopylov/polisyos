# Observation (`polisyos.ir.observation`)

## Purpose

`polisyos.ir.observation` connects raw measurement/panel data to the causal and
policy execution surface. The package defines observation families,
measurement governance, bundle manifests, compiler suites, readiness checks,
and executable causal tasks through which downstream Foundry and Scientist
receive verifiable inputs instead of ad hoc in-memory structures.

## Where to Start

- [`contracts.py`](./contracts.py) — base `ObservationRecord`, `ObservationPanel`, family, and entity-scope contracts.
- [`measurement.py`](./measurement.py) — measurement trust tiers, proxy rules, schema regimes, and identification routing.
- [`governance.py`](./governance.py) — alias registries and mapping observations to the governance/runtime pass surface.
- [`bundles.py`](./bundles.py) — bundle manifests and compatibility targets for downstream contracts.
- [`contract_compilers.py`](./contract_compilers.py) — compiler inputs, artifacts, and serialization helpers.
- [`causal_readiness.py`](./causal_readiness.py) — readiness bundles and persistence helpers.
- [`causal_execution.py`](./causal_execution.py) — executable bounds/temporal DTR tasks and persistence helpers.
- [`bridges.py`](./bridges.py) — standards bridges for SDMX, DDI, FHIR, and CDISC.

## Public entrypoints

| Entrypoint                                                                                    | Use when                                                                                    | Defined in                                     |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| `polisyos.ir.observation.ObservationRecord`, `ObservationPanel`                               | Use the base record/panel contracts                                                         | [`contracts.py`](./contracts.py)               |
| `polisyos.ir.observation.MeasurementRegistry`                                                 | Route by trust tier, proxy rules, and freshness logic                                       | [`measurement.py`](./measurement.py)           |
| `polisyos.ir.observation.SchemaRegimeRegistry`, `RegimeCalendar`, `ShockCalendar`             | Model schema regime shifts and structural breaks                                            | [`measurement.py`](./measurement.py)           |
| `polisyos.ir.observation.ObservationFamilyPolicyRegistry`                                     | Map observation families to governance/runtime passes                                       | [`governance.py`](./governance.py)             |
| `polisyos.ir.observation.ObservationContractCompilerSuite`                                    | Compile observation payloads into Foundry/Scientist-compatible bundles                      | [`compiler.py`](./compiler.py)                 |
| `polisyos.ir.observation.CausalReadinessBundle`                                               | Use the readiness surface for proxy, transportability, counterfactual, and strategic checks | [`causal_readiness.py`](./causal_readiness.py) |
| `polisyos.ir.observation.CausalExecutionBundle`                                               | Use the executable surface for bounds estimation and temporal DTR tasks                     | [`causal_execution.py`](./causal_execution.py) |
| `polisyos.ir.observation.persist_causal_readiness_bundle()`, `load_causal_readiness_bundle()` | Persist/load readiness bundles in CAS-backed flows                                          | [`causal_readiness.py`](./causal_readiness.py) |
| `polisyos.ir.observation.persist_causal_execution_bundle()`, `load_causal_execution_bundle()` | Persist/load an execution bundle                                                            | [`causal_execution.py`](./causal_execution.py) |

## Depends on / depended on by

- Depends on: [`../analytics/README.md`](../analytics/README.md), [`../artifacts/README.md`](../artifacts/README.md), [`../kernel/README.md`](../kernel/README.md), selected `polisyos.foundry` protocol contracts.
- Depended on by: `polisyos.foundry.agent_sim`, `polisyos.foundry.calibration`, `polisyos.foundry.methods`, `polisyos.scientist`, `polisyos.lex`, `polisyos.ir.artifacts.transport`.

## Common commands

Run from the repository root (`policy-engine/`).

Smoke-tested on `2026-04-17`.

```bash
uv run python -c "import polisyos.ir.observation as observation; from polisyos.ir.observation import ObservationRecord, CausalReadinessBundle; print(len(observation.__all__), ObservationRecord.__name__, CausalReadinessBundle.__name__)"
```

## Test/verification commands

Run from the repository root (`policy-engine/`).

Conceptual in this README refresh; run this suite before landing observation
bundle or governance-registry changes.

```bash
uv run pytest tests/unit/ir/observation/test_bundle_schemas.py tests/unit/ir/observation/test_governance_registry.py tests/unit/ir/observation/test_causal_readiness.py tests/unit/ir/test_interoperability_bridges.py -q
```

## Reference docs

- [IR observation reference](../../../../docs/reference/ir/observation.md)
- [IR interoperability reference](../../../../docs/reference/ir/interoperability.md)
- [IR schema catalog](../../../../docs/reference/ir/schema-catalog.md)
- [IR root README](../README.md)
- [Governance README](../governance/README.md)
- [Artifacts README](../artifacts/README.md)

## Last updated

`2026-04-17`
