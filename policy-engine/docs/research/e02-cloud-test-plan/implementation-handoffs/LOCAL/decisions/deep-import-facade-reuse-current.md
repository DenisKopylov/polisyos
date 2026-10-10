# Deep-import facade reuse: current full-set review

**Disposition:** read-only architecture research; no source, contract, baseline, or generated-surface change. The compatible `wire-existing` subset is exactly 82 edges, recorded as a machine-readable receipt below. The other 475 edges are not all routable through current supported contracts. Do not refresh the baseline or alias a package name to make the module-path gate green.

## Pinned measurement

The source receipt is `LOCAL/raw/canonical-final-regeneration-20261010/deep-import-delta.stdout`, SHA-256 `c19e2a68df2fc2f30885791c80a33b224e00f1fd6d81d38d60c08478b768e50f` (705,030 bytes). It records 3,798 current deep-import rows against 3,330 baseline rows (`architecture/baselines/imports/deep_import.json`, SHA-256 `da9b5c9bdaccc4efcdabcd3512f451850e072f24a381d31ad18b16376e8543a7`): 557 added edges, 89 removed, zero same-key metadata changes, and zero detected relocations. The edge renderer hashes to `7965210977caa9dc78394e56c2951d33a11946941047659a8544ee98e7737443`.

The selector is `tools.devx.architecture.guardrails._iter_py_files()`: sorted `src/**/*.py`, excluding `__pycache__`; 2,748 files. The receipt records the canonical compact source-manifest digest `cc3d024fe5455c7509c749101e0a0fcc14d0e7bee9a106314d08c3d9795f65c4` over 419,156 bytes. The retained manifest is an indented JSON view and therefore has a different file hash; compact serialization recomputes to the recorded digest and byte count. The 2,748 manifest rows are present, and all 50 source files plus 11 facade source files in the route receipt match their manifest SHA-256 values.

The candidate HEAD advanced to `d12ae0a32d09d2ec7303008c7f853ef93de72aab` during this review. That commit changes only `tools/devx/workspace/_repo_hygiene.py`; no selected `src/polisyos/**/*.py` file changed. `architecture/public_surface/contract.toml` is `14ae5db4c9f137e2d5b434fd1cdf259151216e7952b50da04218754eef3bdce6` and `tools/devx/architecture/guardrails.py` is `5d30de37ed02c5e346458e62e00b2772e7ba0eed501cf8282f72d3058bf9b4f6` at readback.

## Existing-facade coverage, measured by object identity

I loaded all 38 entrypoints declared in `architecture/public_surface/contract.toml`. For every name on each of the 557 edge records, I compared `getattr(supported_facade, name) is getattr(original_target_module, name)`. A name appearing in `__all__` alone was not counted as a route. I did not run tests, a model fit, or a source mutation.

The complete denominator is 557 `(source_module, target_module)` edges, 951 `(source_module, target_module, imported_name)` occurrences, 479 unique `(target_module, imported_name)` pairs, and 451 distinct imported-name strings. Exact object identity gives this partition:

| Edge class | Edges | Name occurrences | Meaning |
| --- | ---: | ---: | --- |
| Every imported name has a same-object route through a currently supported facade | 82 | included in identity total | `wire-existing` can replace the import at the listed site |
| Some, but not all, names have a same-object route | 32 | included in identity total | The remaining names still need an API decision or another canonical route |
| Facade declares a same-name object but it is a different object | 1 | 1 | Name-only replacement is incorrect |
| No imported name is declared by a same-root supported facade | 442 | — | No current facade route exists |
| **Total** | **557** | **951** | **82 fully routable; 475 are not** |

At the name level: 190 occurrences resolve to the identical object, one is a distinct-object collision, and 760 are absent from all same-root supported `__all__` sets (`190 + 1 + 760 = 951`). The one collision is `MechanismFamily`: `polisyos.ir.analytics.MechanismFamily` is `polisyos.ir.analytics.structural_causal_model.MechanismFamily`, not the different enum at the imported target `polisyos.ir.analytics.mechanism_design.MechanismFamily`.

| Target root | Edges | Name occurrences | Identity-routed names | Fully identity-routable edges |
| --- | ---: | ---: | ---: | ---: |
| `berl` | 2 | 3 | 2 | 1 |
| `common` | 18 | 34 | 0 | 0 |
| `core` | 313 | 453 | 79 | 41 |
| `data_forge` | 26 | 43 | 0 | 0 |
| `fabric` | 8 | 8 | 1 | 1 |
| `foundry` | 32 | 46 | 3 | 3 |
| `ir` | 138 | 329 | 99 | 32 |
| `lex` | 3 | 8 | 4 | 2 |
| `scholar` | 3 | 3 | 1 | 1 |
| `scientist` | 14 | 24 | 1 | 1 |

Same-object name route hits by facade are: `polisyos.berl` 2; `polisyos.core.contracts` 73, `core.security` 4, `core.trace` 2; `polisyos.fabric.api` 1; `polisyos.foundry.uncertainty` 3; `polisyos.ir` 96 and `ir.analytics` 71 (these overlap); `polisyos.lex.knowledge` 4; `polisyos.scholar` 1; `polisyos.scientist` 1. The sum is not an independent total because IR's root and analytics facade export overlapping identities. The route artifact selects the most-specific matching supported facade and preserves alternate same-object routes.

The exact 82-edge patch map, including source file, line, imported name, original target, selected facade, same-object result, alternative identities, and source/facade file hashes, is `LOCAL/raw/deep-import-existing-82-facade-routes.json`, SHA-256 `a96936838c7ff20ebd0cffa3a9388dbf742ef0de892d4ee0b1c4f6a0ad97b0f5` (123,149 bytes; ignored under `LOCAL/raw/`). It is pinned to candidate HEAD `d12ae...` and the compact source-manifest digest above. It includes 50 source-file hashes and 11 facade-source hashes.

## P38: the current guard checks a path proxy, not the imported symbol

`collect_deep_import_edges()` passes only the resolved target module to `_maybe_add_deep_import()` (`tools/devx/architecture/guardrails.py`, around lines 1270–1350). The gate then compares edge keys `(source_module, target_module)` with the baseline (`_check_deep_import_creep()`, around lines 3083–3127). Neither path records nor checks imported names, facade `__all__`, or object identity. A divergent case is `from polisyos.core import artifacts`: the resolved target is the supported `polisyos.core` root and the collector drops it, even if the caller then reaches `ArtifactStore` through the `artifacts` package object. `ArtifactStore` is absent from every currently supported Core facade. This alias is not a route; only the 82 receipt rows were accepted by exact-object comparison.

The observed `MechanismFamily` collision is a second concrete name-proxy falsifier: a same-name facade export exists, but its object differs from the source module's object. Any repair that considers only facade-name membership would pass the wrong class. A future verifier should compare symbol binding/identity (or an equivalent source-owned export mapping) rather than simply allowing `from polisyos.<root> import <subpackage>`.

## Smallest concrete residual contract and P40 classification

P40 bucket: **SAME_CLASS_DEEPER**. The class is cross-package implementation imports bypassing the supported facade boundary; the first proxy finding was target-path membership, and the deeper falsifier is imported-symbol availability and identity. I widened the check from all paths to all 951 edge-name occurrences and tested each candidate against the actual imported object. The residual is no longer a handful of examples: 760 imported-name occurrences have no current same-root public export, and the one same-name collision is explicitly identified. Further per-file import aliases would be instance repairs.

A bounded residual's smallest concrete closure is a deliberate Core owner decision about `polisyos.core.artifacts`. Its package facade already declares 66 exports, including `ArtifactStore`, `ArtifactRef`, `FileSystemCAS`, and `ensure_ir_artifact_store`; the module doc calls it the stable CAS artifact ABI. Yet the supported Core list in `contract.toml` has only `core`, `core.contracts`, `core.observability`, `core.security`, and `core.trace`. Core README says operational subpackages are implementation surfaces until the generated Public Surface is updated. A runtime identity census shows `ArtifactStore` absent from all five current supported Core facades but present as the same object on `core.artifacts` as `core.artifacts.protocol.ArtifactStore`.

As a scale witness, adding that *existing* package facade to the supported-entrypoint contract (not doing so here) would route 270 additional Core name occurrences and 200 additional Core edges: current supported Core coverage is 79/453 names and 41/313 complete edges; the union with `core.artifacts` is 349/453 names and 241/313 complete edges. This narrows the needed owner choice to whether that documented CAS package becomes a supported public entrypoint (with the public-surface inventory/README/identity tests) or remains internal and is consumed via another canonical adapter. It does not authorize exposing all artifact implementation details, nor does it close the remaining Core edges or the other target roots. Similar candidate package facades (`core.canon`, `ir.registry.refs`, `ir.artifacts`, `data_forge.read_api.academic`) also exist but are not current supported entrypoints; adding them is a separate owner/API decision, not automatic coverage.

The shortest falsifier for the residual is a test importing the original `ArtifactStore` use through every current supported Core facade and showing the name absent, then proving the exact existing `core.artifacts` export is identity-equal to `core.artifacts.protocol.ArtifactStore`. The absence case is measured above; the identity case is true. It is therefore not honest to record this residual as “no facade exists”: the facade exists, but the *supported-entrypoint contract* does not admit it. If the owner declines expansion, that is a declared boundary decision and the caller needs a sanctioned cross-root adapter. No such alternate Core adapter has been established here.

## The older 89 removals are not demonstrated closure

The receipt reports `relocation_count=0`; each removed row records source module/file and target module/root, but not imported names or binding provenance. Counts by source family are: Core storage backends 2; Data Forge Catalog source modules/ingest 32 (6 API, 7 loaders, 9 registry, 9 validators, 1 ingest); Ukraine common builder 4; Fabric data-plane modes 2; Foundry treasury 2; Lex simulator 11; Runtime quality acquisition/generation 5; Scientist nodes/orchestration/validation 31. Some current files have sibling helper modules after decomposition, but the raw edge record does not establish which old symbols moved into which helper or whether their contract status changed. Preserve these as 89 removed edges, not 89 proven closures or offsets against the 557 additions.

## Freeze recommendation and exact research write footprint

- Wire only the 82 exact-identity routes in the JSON receipt; retain each import site and do not collapse them through a root subpackage alias.
- Keep the other 475 out of a source-only mechanical patch until package owners decide the supported entrypoints/adapter boundary. In particular, `ir.analytics` documents a curated facade; exposing every advanced analytics implementation symbol would change that boundary.
- Do not refresh `architecture/baselines/imports/deep_import.json` or add a blanket exception. Internal direction permission (all 557 are directionally allowed) is not evidence of a supported public API.
- P41: this note is a read-only review of the current candidate and the complete pinned collector receipt. No gate status is claimed beyond the explicit identity probes. No acceptance of a global baseline is implied.

Only two files were written for this research: this note and the ignored JSON route receipt above. No product source, tracked baseline, generated inventory, or test file was edited; no tests or fits were run.
