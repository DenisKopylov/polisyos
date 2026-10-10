# Independent review: existing-facade deep-import routes

**Result: scoped pass; the deep-import gate remains partial.** The 82 routed edges are exactly the selected portion of the frozen 557-edge delta. I found no changed non-import AST, lost import binding, facade source change, or new deep-import edge in the candidate source slice. This does not close the other 475 edges or establish full-suite behavior.

## Pinned target and evidence

- Baseline/source pin: `d12ae0a32d09d2ec7303008c7f853ef93de72aab` (also the HEAD readback during this review).
- After the recorded checks, HEAD advanced to `30f3c04ffc97ec00a06b9546825be29a8112f65b` for a manifest-only commit; the 50 audited source-file hashes still match the raw receipt, and those source edits remain in the working tree.
- Frozen route input: `LOCAL/raw/deep-import-existing-82-facade-routes.json`, SHA-256 `a96936838c7ff20ebd0cffa3a9388dbf742ef0de892d4ee0b1c4f6a0ad97b0f5`.
- Author's scoped change record: `LOCAL/decisions/deep-import-existing-facade-wire.md`, SHA-256 `9e9f142e6de54eac5fa5d95ae3d8cc28b767c0e65de34e33bcc9d3f429bb5e80`.
- Independent source/collector receipt: `LOCAL/raw/deep-import-existing-facade-independent.stdout.txt`, SHA-256 `403ec942ccb71af601b10c676747a71d0c71db21110b17df2cb8be63250a9b62`.
- Fresh-process import receipt: `LOCAL/raw/deep-import-existing-facade-cold-imports.stdout.txt`, SHA-256 `b85b30520565b540f8f0e38d411136089526eb2f49edb1704fba1c66634fb0bc`.
- The source-side denominator comes from `tools.devx.architecture.guardrails._iter_py_files()` and its frozen input manifest: 2,748 Python files; manifest digest `cc3d024fe5455c7509c749101e0a0fcc14d0e7bee9a106314d08c3d9795f65c4`. The pre-rewrite deep-import receipt is `LOCAL/raw/canonical-final-regeneration-20261010/deep-import-delta.stdout`, SHA-256 `c19e2a68df2fc2f30885791c80a33b224e00f1fd6d81d38d60c08478b768e50f`.

## Property checks

I independently reopened all 50 source files from the pinned base. Their receipt hashes match, and all 82 edge records resolve to the recorded original import line, target module, and ordered imported-name list: 89 import sites and 132 name bindings. Against the candidate source, the full import-binding multiset (including `as` aliases and relative-import levels) matches the expected module rewrites. Removing imports from each parsed AST leaves the remaining AST identical. There are 2,376 import bindings before and after; the 50 changed source files are exactly the 50 files selected by the receipt. Full before/after SHA-256 values are in the independent raw receipt.

All 11 selected facade implementation files still match the route receipt's source hashes. The changed source set contains only routed consumer modules; no public facade, `__all__`, or resource file was edited. In a fresh Python 3.14.3 process with `PYTHONPATH=src:.`, I imported the four named entry modules first—BERL persistence, runtime HTTP container, Scientist compute runner, and Scientist welfare node—then the rest of the 50-route-module set. All imports resolved to this worktree. I also checked exact object identity for all 76 distinct `(original symbol module, name, selected facade)` triples used by the 132 binding occurrences; all passed.

I reran the actual `collect_deep_import_edges()` implementation over the source tree and compared its exact edge-key set against the frozen pre-rewrite candidate delta. The 82 selected keys are gone; the remaining added set is exactly the original 475 keys. Baseline accounting remains 3,330 edges, with the original 89 removed baseline keys; current collector count is 3,716. There are no extra or missing keys relative to `baseline - original removals + original additions - selected routes`.

## Findings, limits, and class disposition

No blocking finding in the selected routes. The imported bindings retain their names and aliases, and the selected facades expose the exact original objects. The author-reported Ruff check and formatting check were not rerun independently; this review executed the AST, identity, collector, and cold-import checks above, not pytest or a package-wide suite.

P38 remains relevant to the *guardrail*: its deep-import collector compares module-edge keys, not imported names or object identity. A same-name but different-object facade binding (the recorded `MechanismFamily` collision) is a concrete divergence. This patch avoids that divergence for its selected routes through the separately measured object-identity mapping; it does not make the guardrail itself an identity gate.

P40 classification: **same deep-import-creep class, one level deeper** (consumer edge → symbol/facade binding). The bounded residual is the exact 475 unselected edges: 32 partial facade matches, one identity collision, and 442 with no candidate supported-facade export in the frozen census. The residual falsifier is the full collector reconciliation above; any selected edge remaining or any edge outside that expected set fails it. Closing the residual needs a supported, owner-approved facade route for the relevant symbols or a separately approved API decision; this slice does not make that decision. The full deep-import gate therefore remains unresolved/partial, not green.

This is an import-surface maintenance change, so P06 (canonical-vs-deep/shim ownership) and P38 (module-edge proxy) are the relevant patterns. Existing facade reuse is evidenced for the selected routes; the separate decision about residual surface ownership remains open.
