# Bounded wire-existing deep-import routes

This slice rewires only the complete exact-object routes already exposed by supported public facades. It does not change the public-surface inventory, generated baseline, facade exports, or API behavior.

## Frozen evidence and scope

- Candidate source base: `d12ae0a32d09d2ec7303008c7f853ef93de72aab`.
- Route receipt: `LOCAL/raw/deep-import-existing-82-facade-routes.json`, SHA-256 `a96936838c7ff20ebd0cffa3a9388dbf742ef0de892d4ee0b1c4f6a0ad97b0f5`.
- The receipt selects 82 complete same-object module edges out of the 557-edge delta, across 50 source files. The source AST census found 89 import sites and 132 imported-name bindings in this selected set. All 50 recorded source hashes matched the candidate base before rewrites.
- The remaining 475 delta edges are outside this mechanical slice: 32 are partial same-object routes, 1 has an object-identity collision, and 442 have no candidate public export. This does not claim the full deep-import gate is green.

## Change and verification

Imports were routed to each symbol's selected most-specific supported facade, preserving imported names and `as` aliases. A mixed-facade import was split by selected facade while preserving each binding. A now-unused `TC001` noqa on `ControlJobResponse` was removed after the facade move made Ruff report it unused.

Readback checks against the frozen base and route receipt reported:

- `BASE_HASHES_OK files=50`.
- `AST_IMPORTS_SEMANTICALLY_PRESERVED files=50 routes=82 import_sites=89 symbols=132`; module differences are exactly the receipt's selected facade routes and aliases are unchanged.
- `RUNTIME_EXACT_OBJECT_IDENTITY_PASS imported_names=132 module_edges=82`; each selected facade attribute is the identical object exported by the original symbol module.
- Ruff check on the 50 explicit source paths: `All checks passed!`.
- The initial format check identified one formatting companion in `src/polisyos/runtime/quality/data_state_substrate.py`; it was formatted in a separate, single-file step after comparing normalized AST and import bindings.
- Final Ruff check and format check on the same 50 explicit source paths both pass. The full-object-identity check was rerun after formatting and still passes all 132 names.

The route receipt is ignored local evidence, not a new inventory or contract. The unresolved edges require separate source/API decisions and remain explicitly out of scope here.

## Final formatting companion

`src/polisyos/runtime/quality/data_state_substrate.py` changed from SHA-256 `30e195588c0d01d4e929c90929fd50107f3cc81080e47ed3e3dbc2a1103a173e` to `c25fbfb29cd86437548518295cc4f5df18294d6ec4dc73d688e1daae2f2c921d` after formatting that single file. The normalized AST and 78 import bindings are identical before and after. Final scoped commands report `All checks passed!` and `50 files already formatted`; the post-format runtime identity check passes all 132 imported names.
