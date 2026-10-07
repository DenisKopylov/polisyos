# B CAS/durability evidence delta — 2026-10-07 11:46 intake

**Disposition: metadata/evidence GO; no code acceptance or finding closure.** G input is `855cb26a7a2c9fea60356663cf81e7d01e20c738` / tree `2e228785406834ba128bb7b4dd9c636a6a2a1cb5`. The two pinned remote advances are descendants of their old pins and each changes only handoff/evidence paths:

- CAS generation: `74be8fa5…` → `8c292c49…` / tree `954606c6…`, 15 paths.
- Durability: `e3e8cab0…` → `0bf268e7…` / tree `e039e83b…`, 8 paths.

Both diffs have zero `src/`, `tests/`, or release-fragment paths. The source-level code candidate referenced by these receipts is separately `7c05686dbd8427fa2e8bf217827046acef097058` / tree `1c705c31775935039c2823b0c70f9f1f090f1411`, descended from `e82ac583…`. That source’s four owned changes are the identity implementation, its README, `test_module_source_identity.py`, and the release fragment. They are not changes in either new metadata carrier.

## CAS source review and existing author wave

CAS handoff `continuation-getter-source-independent-review.json` pins the exact source `7c05686…`, reports `closure_ids=[]`, and limits its conclusion to the ordinary-function finite getter family. Its evidence index names 13 files / 125,042 bytes; all 13 size/SHA pairs match Git objects at `8c292c49…`.

The audit sequence is mixed and must stay so: first source audit **ERROR** (two audit errors: a 76-path stale comparison against intervening evidence and an assertion-name/input mismatch); corrected source audit **PASS** with zero audit errors; peer evidence reconciliation **PASS**; author payload reconciliation **PASS**. The first error is retained as audit history, not a product-source failure. The independent source reviewer explicitly records its own native execution as **UNRUN**.

The author’s immutable root-binding index is at `db1e001c…`, SHA `4e6679bf…8000`; it binds source `7c05686…` / `1c705c…` and 94 payloads totaling 760,092 bytes. I verified every payload’s committed size and SHA. The 24 `.lossless.json` envelopes decode by their `raw_bytes` / `raw_sha256` fields with zero mismatches (117,398 decoded bytes). This is distinct from hashing the JSON wrapper itself.

Those author outputs preserve the already reviewed five-file cohort: 128 cases, **127 PASS / 1 FAIL**, 168 module origins. The lone failure is the real B74 frame/global-namespace replacement: resumed value 107 instead of 7, with `original, original, replacement` physical effects and no refusal. The separate getter-admission-removal control is **1 expected FAIL**: the output explicitly says all finite data-getter admission was disabled while source files remained unchanged, so the supported numeric consumer was refused. The 3 old lexical collision failures belong to their older source pins; the four root-collision cases pass on `7c`. Ruff, format and normal-import mypy are reported PASS on the same author evidence. These are not new runs from the CAS carrier.

## Durability’s new exact consumer run

The 0bf handoff adds a distinct, narrow native run on exact source `7c05686…` / tree `1c705c…`, not a rerun of the 128-case cohort. Its literal test is `test_independent_getter_consumer.source.txt` at `cc5de5db…`; the 5,272-byte Git blob matches SHA `c60de7f7…5559`. The receipt’s source before/after is identical and clean. Its six-file evidence index totals 51,293 bytes; every indexed Git size/SHA matches.

The complete native stdout and JUnit agree: **3 PASS / 0 FAIL / 0 ERROR / 0 SKIP** (1.76s pytest; 2.51s supervisor). It exercises eager and JAX compiled `MethodCompiler` handles for cold/warm/dynamic override/old-handle replay, plus a captured `ModuleType` getter refusal before the physical method-body file appears. Numeric score/spread vectors match the oracle for all eight eager/JIT states. The profile binds 152 loaded file-backed `polisyos` origins; I independently compared every path, size and SHA with source `7c`, with 152 matches and zero mismatches. This PASS is for the three-case finite consumer, not B74’s frame case or a complete B/JIT wave.

The captured-ModuleType refusal is a behavioral negative consumer case; it is not a property-removal experiment. The distinct author removal control above is the removal result. Neither erases B74’s actual frame failure.

## Relation to G’s prior B decision

The pinned 855 tenth-wave B review already records the same `7c` five-file result, 128 = 127 PASS / 1 B74 FAIL, plus canonical JIT 9 PASS and one removal-control FAIL. The new author-index reconciliation confirms those exact counts and source identity; the new durability run adds three bound consumer cases. No outcome is transferred to a different source, and no finding is closed. B74 remains LIMITED; global B/source-quality acceptance and G integration acceptance remain separate.

All updated evidence indexes and receipt files are present and hash-consistent. No tests, source, refs, integration files, or other tracked files were changed.
