# Independent review: CatalogRunProfile facade export

## Decision

**GO to apply this four-path companion patch.** It makes the existing lazy `CatalogRunProfile` symbol a declared `polisyos.core.contracts` export, adds a runtime object-identity control, documents the import path, and records the additive Python API change. The patch changes no Literal values, DTO fields, schema, or source implementation.

This is a static review only; I did not apply the patch or execute tests. It covers only the exact export companion, not the larger import-edge census, any uncovered-edge closure, or API semantics outside this alias.

## Patch and preimages

- Patch: `LOCAL/raw/architecture-companion-export-resolution-proposal.patch`, SHA-256 `47c9fc41cc6a27fd5488d4dffc35311ceb56ca46a0633ef6b7ae9cd8fd33be15`.
- Current preimage hashes: facade `src/polisyos/core/contracts/__init__.py@0657d75eb8c5b5568e730b40097a5bb9a59b0e26828eadf1418dbcf2300ccfdd`; defining alias `control.py@a2cc9c46829147a9f3b72796987e7aae61b09e2af81556d8e5e08e2778f3959d`; README `README.md@1df86638e2521db73ca6c65d8a25004832d29a26a4449d2dacace1a535e0cde5`; test `test_public_surface_export_resolution.py@c256fd69a52502adf79d2a3e7f8b02c87fd8f9b843ca87b84b7e0d47786b8c79`.
- The patch adds one `__all__` entry, one identity test, one README bullet, and one release fragment. No existing export is removed or reordered beyond the single sorted insertion.

## Contract identity and release metadata

The current facade’s `_MODULE_SYMBOLS[".control"]` already maps `CatalogRunProfile` to `polisyos.core.contracts.control`; the facade’s lazy `__getattr__` resolves through that mapping. The defining symbol is the existing `Literal[...]` in `control.py`. Adding it to the explicit `__all__` therefore exposes the same object through the canonical facade. The added test checks both declaration and identity (`contracts.CatalogRunProfile is control_profile`), which is the right contract for a pure re-export.

The release fragment calls the change additive and states that the Literal object and values are unchanged. It also says the public-surface inventory currently reports the facade exports as unknown, and explicitly avoids claiming that this export fixes that inventory. I read `public_surface_inventory_reviewed = true` as the required acknowledgement that the public API was reviewed, not as a claim that the inventory is complete; the limitation text preserves that distinction.

## Scope boundary

The patch is compatible with existing imports from `polisyos.core.contracts.control` and makes the facade path available for explicit and wildcard imports. It does not alter the Data Forge read facade or other `CatalogRunProfile` names, nor does it establish wider architectural import coverage. Any decision about the remaining deep-import edges or their semantics must be reviewed separately; this patch provides no basis to close those rows.
