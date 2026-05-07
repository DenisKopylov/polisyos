# Fabric Product/API Integration

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Freshness: 2026-04-28.
Owner: `@fabric-owners`
Source of truth: `src/polisyos/runtime/http/routes/fabric.py`, `src/polisyos/runtime/http/services/fabric.py`, `src/polisyos/fabric/product_integration.py`, `src/polisyos/fabric/compatibility.py`, `apps/runtime-dashboard/src/test/contracts/**`, `tools/quality/validation/fabric_product_integration.py`

Fabric Phase 10 closes the loop between governed data and downstream product
surfaces. Runtime exposes additive endpoints for scorecards, quality/trust
batch lookup, replay, and impact analysis; frontend fixtures prove Design Wave
2 can render the payloads; Scientist, Scholar, Lex, and Foundry consume the
same Fabric trust metadata instead of building separate provenance shortcuts.

## Runtime Endpoints

| Surface | Endpoint | Purpose |
| ------- | -------- | ------- |
| Source scorecards | `GET /api/v1/fabric/source-scorecards` | Return committed source scorecards with freshness, reliability, schema drift, quality, replay, latency, and trust dimensions |
| Quality batch | `POST /api/v1/fabric/quality/batch` | Batch-fetch `QualityRef` rows for decision-data ids without N+1 lineage reads |
| Trust batch | `POST /api/v1/fabric/trust/batch` | Batch-fetch lineage, access, replay, source-contract, and temporal trust metadata |
| Replay | `GET /api/v1/fabric/runs/{run_id}/replay` | Return replay refs and status counts for a run |
| Impact analysis | `POST /api/v1/fabric/impact` | Answer downstream impact for lineage ids and source-contract ids |

The endpoints are additive and published through the committed Runtime OpenAPI
snapshot and generated runtime API client. Existing lineage and temporal
surfaces remain intact:

| Existing surface | Phase 10 role |
| ---------------- | ------------- |
| `POST /api/v1/lineage/batch` | Compact/full lineage batch lookup for provenance hover and Trust View |
| `GET /api/v1/temporal/capabilities` | Branch, snapshot, temporal-scope, and graph-temporal capability disclosure |
| `GET /api/v1/runs/{run_id}/fabric-decision-data` | Trust envelopes for decision-bearing values |

## Frontend Fixtures

The Runtime dashboard contract suite now carries product fixtures for the
Design Wave 2 affordances that depend on Fabric:

| Fixture | Product affordance |
| ------- | ------------------ |
| `run-quantities.json` | Quantity rendering |
| `run-fabric-decision-data.json` | Fabric trust envelopes |
| `lineage.json` and `lineage-batch.json` | Provenance-on-hover and full lineage views |
| `temporal-capabilities.json` | Temporal scrubber capability disclosure |
| `compare-run.json` | Policy diff |
| `counterfactual-metrics.json` | Counterfactual layer |
| `fabric-source-scorecards.json` | Source trust and reliability panels |
| `fabric-quality-batch.json` and `fabric-trust-batch.json` | Trust View batch metadata |
| `fabric-replay.json` | Replay status |
| `fabric-impact.json` | Impact analysis |

`fabricDecisionDataToQuantityValue()` converts `FabricDecisionData` envelopes
into the shared `QuantityValue` shape, preserving lineage status, temporal
scope, source contract, quality, access, replay, and `fabric_trust_envelope`
metadata for Trust View. `useRunFabricDecisionData()` fetches
`/api/v1/runs/{run_id}/fabric-decision-data` and exposes both raw Fabric rows
and renderable quantities.

## Governance Consumers

| Consumer | Integration |
| -------- | ----------- |
| Scientist | `FabricTrustGatePass` caps decision readiness when Fabric quality fails, lineage is missing, evidence is stale, access is restricted, or source trust is low |
| Scholar | `scholar_citation_from_fabric_decision_data()` converts Fabric trust envelopes into citation-ready provenance records |
| Lex | `lex_evidence_from_fabric_decision_data()` carries raw evidence refs, replay status, and access classification into legal evidence paths |
| Foundry calibration | `fabric_calibration_context_from_decision_data()` derives conservative calibration weights from Fabric quality, freshness, and source trust |
| Foundry uncertainty | `fabric_uncertainty_context_from_decision_data()` inflates uncertainty for failed, stale, or non-replayable Fabric evidence |

## Compatibility Bridges

Every compatibility bridge has an owner, reason, sunset date, and migration
issue in `polisyos.fabric.compatibility`.

| Bridge | Owner | Sunset | Migration issue |
| ------ | ----- | ------ | --------------- |
| `runtime.fabric_decision_data_v1` | `@fabric-owners` | 2026-09-30 | `FABRIC-P10-runtime-decision-data-native` |
| `runtime.quantity_value_compat` | `@runtime-owners` | 2026-08-31 | `FABRIC-P10-quantity-envelope-unification` |
| `frontend.runtime_api_client_compat` | `@runtime-owners` | 2026-10-31 | `FABRIC-P10-generated-client-sunset-review` |
| `scientist.fabric_trust_gate_compat` | `@scientist-owners` | 2026-09-15 | `FABRIC-P10-scientist-native-trust-gate` |
| `product.fabric_evidence_path_adapter` | `@fabric-owners` | 2026-11-30 | `FABRIC-P10-product-native-evidence-paths` |

`polisyos.fabric.__all__` stays stable for Phase 10. Product adapters are
available through their module paths and product package facades, while the
root Fabric facade remains governed by the existing public-surface policy.

## Validation

```bash
uv run python tools/quality/validation/fabric_product_integration.py --check
uv run pytest tests/unit/runtime/http/test_fabric_integration_routes.py -q
uv run pytest tests/repo_quality/tools/test_fabric_product_integration.py -q
uv run pytest tests/unit/fabric/test_product_integration.py tests/unit/scholar/test_fabric_provenance.py tests/unit/lex/test_fabric_provenance.py -q
uv run pytest tests/unit/foundry/calibration/test_fabric_quality.py tests/unit/foundry/uncertainty/test_fabric_quality.py -q
corepack pnpm --filter @polisyos/runtime-dashboard run test:contracts
corepack pnpm --filter @polisyos/runtime-dashboard exec vitest run src/shared/ui/quantity/fabric-decision-data.test.tsx src/api/hooks/useRunFabricDecisionData.test.tsx
```

::: polisyos.fabric.product_integration

::: polisyos.fabric.compatibility
