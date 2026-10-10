# Independent review: CatalogRunProfile generated companions

## Decision

**GO for the two generated companions.** The source digest in the inventory matches the current `core/contracts/__init__.py` bytes, and the regenerated reason string records the new `CatalogRunProfile` name while preserving the facade’s unresolved status. No broad export resolution or unknown-to-known promotion is visible in these outputs.

This is a read-only delta review. I did not run tests, invoke the renderer, or use Git.

## Exact readback

- Renderer receipt: `LOCAL/raw/catalog-run-profile-generated-readback-20261010/surgical-regeneration.json@8aedb681f03c2d5d986f64210038756a85e6daafab93271f761d5e761dc9cf6d`.
- `architecture/public_surface/inventory.json`: current SHA-256 `2f66b5677ac2df639d2d42f0e362e809ab4579603b6b11704b2dc4afd7f43df9`; receipt reports previous SHA `9e4bdbf3772894f335512c2afd7f27cc03e206475790c0338a74feedabc3b924`, changed lines 585, 586, and 619, with `exact_canonical_bytes = true`.
- `docs/reference/public-surface.md`: current SHA-256 `5c56a5d804867e2f24757f95db06a4e6e7b4e71eca3460699c7c813fc641364d`; receipt reports previous SHA `c6dd74692dbd798b5bd44d21f81e5af71c81edeb220d03f07430785dad00422f`, changed line 346, with `exact_canonical_bytes = true`.
- Current source `src/polisyos/core/contracts/__init__.py` SHA-256 is `263a140bdce75e6e9ce2f6c6b31c3bff43b8c0a91a26fb886f59e6e8e8341e6e`, matching the inventory’s `read_bytes` SHA and reported byte count `62279`.

## No broad resolution claim

The generated row remains `facade_mode_observed = "unresolved_exports"`, `export_count = null`, `known_export_count = 0`, `exports = []`, and `export_resolution.complete = false`. The reason string includes `CatalogRunProfile` in the unresolved `__all__` expression; it does not classify that name, or any other name, as a proven export. The rendered reference likewise continues to say `Facade: unresolved_exports` and reports the incomplete export expression.

These outputs are therefore consistent with the reviewed additive facade export while preserving the independent inventory’s current inability to resolve the starred chronology expression. The two generated files do not close any wider import-edge or public-surface inventory findings. This review covers only the generated companions for this one export.
