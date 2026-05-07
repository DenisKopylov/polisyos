# Repository Best-In-Class Phase 5.7 Package README Coverage

Date: 2026-05-06
Owner: `team-docs`
Status: passed

## Scope

Phase 5.7 requires README/AUTHORING coverage for public-stable and
high-complexity packages. The package README contract now uses these fields:

- `## Purpose`
- `## Public API`
- `## Internal Layout`
- `## Extension Points`
- `## Tests`
- `## Operability Links`
- `## Known Shims/Deprecations`

No MkDocs nav files were changed.

## Public-Stable Package Coverage

| Package | README | Notes |
| --- | --- | --- |
| `polisyos.common` | [src/polisyos/common/README.md](../../../src/polisyos/common/README.md) | Stable facade, tests, operability, and no-shim statement documented. |
| `polisyos.core` | [src/polisyos/core/README.md](../../../src/polisyos/core/README.md) | Shared contracts, component bootstrap, SLO/runbook, and no-shim statement documented. |
| `polisyos.ir` | [src/polisyos/ir/README.md](../../../src/polisyos/ir/README.md) | Root facade, schema workflow, IR shims, and high-complexity analytics budget documented. |
| `polisyos.fabric` | [src/polisyos/fabric/README.md](../../../src/polisyos/fabric/README.md) | Root facade, connector extension point, Fabric shims, SLO/runbook links documented. |
| `polisyos.foundry` | [src/polisyos/foundry/README.md](../../../src/polisyos/foundry/README.md) | Compile/execute facade, method extension path, synthetic-world shim, operability links documented. |
| `polisyos.scientist` | [src/polisyos/scientist/README.md](../../../src/polisyos/scientist/README.md) | Workflow facade, node/pass extension points, Scientist lane shims, operability links documented. |
| `polisyos.runtime` | [src/polisyos/runtime/README.md](../../../src/polisyos/runtime/README.md) | Replay facade, HTTP service boundary, middleware extension point, runtime budgets documented. |
| `polisyos.lex` | [src/polisyos/lex/README.md](../../../src/polisyos/lex/README.md) | Runtime legal facade, NormPack extension point, Data Forge boundary, operability links documented. |

## High-Complexity Package Coverage

| Package/Subtree | README | Budget/Contract Link |
| --- | --- | --- |
| `polisyos.foundry.methods` | [src/polisyos/foundry/methods/README.md](../../../src/polisyos/foundry/methods/README.md) | [architecture/module_size_budget.toml](../../../architecture/module_size_budget.toml) |
| `polisyos.foundry.methods.catalog.causal` | [src/polisyos/foundry/methods/catalog/causal/README.md](../../../src/polisyos/foundry/methods/catalog/causal/README.md) | Causal budgets, characterization tests, and extension rules documented. |
| `polisyos.scientist.nodes` | [src/polisyos/scientist/nodes/README.md](../../../src/polisyos/scientist/nodes/README.md) | Decision-packet node budget and node extension contract documented. |
| `polisyos.data_forge.domains.catalog.batch` | [src/polisyos/data_forge/domains/catalog/batch/README.md](../../../src/polisyos/data_forge/domains/catalog/batch/README.md) | `core_sources_ingest.py` budget and Data Forge domain extension contract documented. |
| `polisyos.runtime.http.services` | [src/polisyos/runtime/http/services/README.md](../../../src/polisyos/runtime/http/services/README.md) | `control.py` budget, OpenAPI compatibility, and runtime operability links documented. |
| `polisyos.ir.analytics` | [src/polisyos/ir/analytics/README.md](../../../src/polisyos/ir/analytics/README.md) | Existing README/AUTHORING/index coverage remains green; root IR README links the strategic budget. |
| `polisyos.fabric` facade cleanup | [src/polisyos/fabric/README.md](../../../src/polisyos/fabric/README.md) | Active Fabric facade shims linked to [architecture/shims.toml](../../../architecture/shims.toml). |
| `polisyos.ir` facade cleanup | [src/polisyos/ir/README.md](../../../src/polisyos/ir/README.md) | Active IR facade shims linked to [architecture/shims.toml](../../../architecture/shims.toml). |

## Owner/Sunset Exceptions

None. All public-stable package READMEs exist, all targeted high-complexity
package READMEs exist, and active shims/budgets are linked to their owning
architecture contracts instead of being treated as undocumented exceptions.

## Verification

```bash
pytest -q tests/repo_quality/architecture/test_repository_best_in_class_phase4_10_directory_docs.py
```

Result on 2026-05-06:

```text
.....                                                                    [100%]
```
