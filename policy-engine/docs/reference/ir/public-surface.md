# IR Public Surface

Related explanation: [Trinity](../../explanation/trinity.md).

> Package-level IR facades are now explicit, lazy, and export-audited.

The broad compatibility boundary remains `polisyos.ir`. The package facades
below serve a different purpose: predictable tooling/discovery imports that do
not eagerly load whole dependency trees.

Freshness: 2026-04-26
Owner: `@ir-owners`
Source of truth: `src/polisyos/ir/api.py`, `src/polisyos/ir/__init__.py`, `src/polisyos/ir/analytics/__init__.py`, `src/polisyos/ir/kernel/__init__.py`, `src/polisyos/ir/world/__init__.py`, `tests/unit/ir/test_public_surface.py`
Source plan phase: D1-L4 Phase 3 public surface cleanup and hot-path import optimization.

## Facade Inventory

| Facade | Symbol count | Import policy |
| --- | --- | --- |
| `polisyos.ir.analytics` | 260 | curated lazy facade |
| `polisyos.ir.kernel` | 52 | full lazy facade |
| `polisyos.ir.world` | 54 | full lazy facade |

Advanced or module-specific APIs should be imported from their defining
submodules, for example `polisyos.ir.analytics.causal_graph`,
`polisyos.ir.analytics.interference`, or `polisyos.ir.analytics.strategic`.

## Naming Conventions

| Pattern          | Meaning                                         | Policy                                                                                                                     |
| ---------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `_id`            | Stable domain identifier                        | Use for author-controlled, referential identifiers such as `policy_id`, `slot_id`, `metric_id`.                            |
| `_ref`           | Typed reference to another artifact or contract | In IR prefer `ArtifactRefModel` or typed `*Ref` classes; reserve raw `ArtifactRef` naming for core/runtime manifest types. |
| `*_key`          | Derived lookup/cache key                        | Use only for reproducible derived keys such as canonical request/cache identifiers, never for mutable business identity.   |
| `ArtifactRef`    | Runtime/core manifest name                      | Treat this as a core/runtime boundary term; IR surfaces should expose typed refs instead of untyped artifact payloads.     |
| `RegistryItemId` | Registry fragment/linker diagnostic key         | Conceptual label for registry item keys used in composition and reporting, not a separate wire-format object.              |

## Export Audit

- The source of truth for package facades lives in `polisyos.ir.api`.
- Tests verify that documented facade counts match the code manifest and that
  importing package facades does not eagerly import their full submodule trees.

- `polisyos.ir.analytics` is intentionally curated: if a symbol is not listed in
  its package facade, import it from the specific analytics submodule instead.

- The analytics/world counts now also include supported interoperability bridge
  exports (causal ecosystem exchange and PROV-O mapping).

- The analytics facade now includes the supported spatial interference / MAUP
  contract family used by phase-2 aggregation-invariance diagnostics.

- The analytics facade also includes the Phase 2 network-generative block-bridge
  contracts used to carry SBM design strata into causal estimation.

- The analytics facade also includes the Phase 3 welfare/GE uncertainty bundle
  contracts used by welfare propagation and decision-packet aggregation.

- The analytics facade also includes the Phase 4 regime-shift forecast bundle
  contract used to gate long-horizon forecasts under structural breaks.

- The analytics facade also includes the Phase 4 exact ABM, microsim validation,
  temporal graph, space-time causal, and welfare multiplicity closure contracts.

- The analytics facade also includes the Phase 5 shift-diagnostic contract,
  operating-characteristic library, and readiness-impact surfaces consumed by
  `PredictionResult` workflows.

- The analytics facade also includes the Phase 5 dependent-copula sensitivity
  bundle/result contracts used for correlated-input sensitivity analysis.

- Validation hooks: `tests/unit/ir/test_public_surface.py` for IR package facades and
  the public-surface renderer in `polisyos-tools architecture guardrails` for the
  generated repository inventory.
