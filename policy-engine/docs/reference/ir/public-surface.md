# IR Public Surface
Related explanation: [Trinity](../../explanation/trinity.md).

> Package-level IR facades are now explicit, lazy, and export-audited.

The broad compatibility boundary remains `polisyos.ir`. The package facades
below serve a different purpose: predictable tooling/discovery imports that do
not eagerly load whole dependency trees.

Freshness: 2026-04-17
Owner: `@ir-owners`
Source of truth: `src/polisyos/ir/public_surface.py`, `src/polisyos/ir/__init__.py`, `src/polisyos/ir/analytics/__init__.py`, `src/polisyos/ir/kernel/__init__.py`, `src/polisyos/ir/world/__init__.py`, `tests/ir/test_public_surface.py`
Source plan phase: D1-L4 Phase 3 public surface cleanup and hot-path import optimization.

## Facade Inventory

| Facade | Symbol count | Import policy |
|--------|--------------|---------------|
| `polisyos.ir.analytics` | 95 | curated lazy facade |
| `polisyos.ir.kernel` | 52 | full lazy facade |
| `polisyos.ir.world` | 54 | full lazy facade |

Advanced or module-specific APIs should be imported from their defining
submodules, for example `polisyos.ir.analytics.causal_graph` or
`polisyos.ir.analytics.strategic`.

## Naming Conventions

| Pattern | Meaning | Policy |
|---------|---------|--------|
| `_id` | Stable domain identifier | Use for author-controlled, referential identifiers such as `policy_id`, `slot_id`, `metric_id`. |
| `_ref` | Typed reference to another artifact or contract | In IR prefer `ArtifactRefModel` or typed `*Ref` classes; reserve raw `ArtifactRef` naming for core/runtime manifest types. |
| `*_key` | Derived lookup/cache key | Use only for reproducible derived keys such as canonical request/cache identifiers, never for mutable business identity. |
| `ArtifactRef` | Runtime/core manifest name | Treat this as a core/runtime boundary term; IR surfaces should expose typed refs instead of untyped artifact payloads. |
| `RegistryItemId` | Registry fragment/linker diagnostic key | Conceptual label for registry item keys used in composition and reporting, not a separate wire-format object. |

## Export Audit

- The source of truth for package facades lives in `polisyos.ir.public_surface`.
- Tests verify that documented facade counts match the code manifest and that
  importing package facades does not eagerly import their full submodule trees.
- `polisyos.ir.analytics` is intentionally curated: if a symbol is not listed in
  its package facade, import it from the specific analytics submodule instead.
- The analytics/world counts now also include supported interoperability bridge
  exports (causal ecosystem exchange and PROV-O mapping).
- Validation hooks: `tests/ir/test_public_surface.py` for IR package facades and
  the public-surface renderer in `tools/architecture/guardrails.py` for the
  generated repository inventory.
