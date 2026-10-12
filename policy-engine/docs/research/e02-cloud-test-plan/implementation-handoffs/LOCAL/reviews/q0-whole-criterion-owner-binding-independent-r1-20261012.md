# Q0 whole-criterion / owner-binding consumer review

**Decision:** GO for the virtual, report-only fail-closed projection; BLOCK for treating this as a registered, replayable criterion-to-owner alignment capability or as candidate/G authority.

The reviewed source checkpoint is branch `codex/e02-unified-local-20261009`, HEAD `512ad7fede6fdc40e86066630fd63df5b2c11161`, tree `887ba4d0e59a604f71409a45bedd0189ca684999`. The proposed patch targets the ignored report builder `LOCAL/raw/q0-full-occurrence-report-author-20261011/virtual_emitter.py` at SHA-256 `8aea1349580570fd4c73869072e0abb4f4cb8bc8deb096dafc7639ff32d04afb`. Patch SHA-256 is `4b56eb6313d2fedd9b057bb502f0d75dab1987b63e0a9996d0998c6edda10dd4`; its virtual output SHA-256 is `34ce0e9c2202dea04d5113beb3d8fbd5e3e64ca76e27df9fd4a24af7753b678d`. The patch passes `git apply --check --verbose` with zero fuzz and was not applied.

## Property and observed behavior

The property is that an owner-scoped mechanism must not be admitted as the original whole criterion without an independently source-qualified semantic binding. The virtual patch sets `whole_property.owner_assessed_property` to null on all 291 rows, preserves the owner mechanism under its bounded path and explicit owner-scope pointer, binds the original criterion to its coverage identity and source span, and fixes every alignment state at `not_established`. It does not synthesize a positive or partial match.

The patched packet validator re-derives the 291 criterion identities from coverage, checks the source commit/blob and exact span hashes, requires the owner row identity multiset, and compares the projected bounded mechanism and owner pointer to the supplied owner draft. Its exact marker/removal controls reject all 291 cases where criterion/owner bindings are removed while status markers stay and the direct owner value is restored. The LA-033 and B26 self-labelled-positive controls, plus criterion hash, owner pointer, and source-span drift controls, also reject.

I independently reran the helper with `python3 -B .../virtual_projection.py --check`. It exited 0; its 14,843-byte stdout is SHA-256 `7dafaf2bd579205495ef8e4060a7c68ea73aab48a0617ebe3fdabc59478358db`, stderr is empty, and all five generated artifacts passed byte readback. The report retained 282 finding IDs, 291 unique occurrence identities, 319 distinct task-assignment references, and 331 expanded occurrence routes. Candidate states remain `UNRUN` for all 291; formal G is `not_adjudicated`; formal closure IDs are empty; 198 historical source-author closed IDs and B198 are preserved.

The registered producer `LOCAL/emit_proposals.py` at SHA-256 `4d5e70c67f62af07cdb7d3313ad3caa2a689172888b44051c13bb07e6dbbacec` contains no `whole_property` or `owner_assessed_property` fields. The proposed patch changes only the separate ignored report builder; a search of product `src`, `tests`, and `tools` found no consumer of these fields. This is a local review-projection correction, not a product capability or registered producer change.

## Source and authority boundary

Original criterion references are independently reconciled to pinned Git source objects and span hashes. That evidence supports criterion identity, not semantic alignment with the owner assertion. For example, LA-033’s source is a replay compatibility migration while its owner property concerns checkpoint PII scan state. B26’s source is a pairwise-versus-global additivity boundary while its owner property concerns persisted cubic N5 results and fresh N8 consumption. These are the same P40 class at different depth: B26 is `SAME_CLASS_DEEPER` than LA-033; the patch appropriately widens the direct-property guard across all 291 rows rather than filtering those examples.

The owner input is materially less durable. `LOCAL/crosswalk/occurrence-evaluations-draft.json` is 3,164,592 bytes with SHA-256 `82d6fcfe2b8f74b725e51a19467b5aa4a506788f3c7349ae5c41599ba775d339`, but it is untracked and has no Git object in this checkout. Its computed blob ID `89bf9a3e430c053533acfb3d748212d7db95c0cb` is absent from the object store; the file has only a local `0644` mode. The preimage declaration binds its current bytes by SHA-256, and the local `--check` verifies that hash, but the decision packet itself binds the owner assessment by path and JSON pointer only; it does not carry the declaration SHA or an owner-source blob/mode identity. A future reader cannot replay the owner side from the packet alone.

P37 classification: original criterion identity and source-span hashes are `independently_reconciled`; occurrence-set counts are `recomputed`; the owner’s property truth and its scope are `consumer_asserted`; durable owner-source Git identity and criterion/owner semantic alignment are `not_established`. The positive criterion-to-owner alignment capability is `absent/unallocated`: there is no typed independent basis producer or registered consumer. No candidate or formal authority is inferred from the successful projector checks.

## Residual and next falsifier

The main direct-field guard behaves as intended, but the patched `validate_packet` does not bind every sibling projection copied into `whole_property`. In a direct in-memory call to that actual patched validator, restoring the direct owner field, changing the nested bounded owner property, changing the owner pointer, self-labelling a positive alignment, and making the bounded mechanism malformed were rejected. Mutating only `proxy_divergence`, `readout`, or `remaining_quantity_or_dependency` was accepted. These values remain owner-derived; the output’s `criterion_owner_alignment` still says `not_established`, so this did not create a positive alignment, but the validator is incomplete as a general integrity gate for the whole report object. The `--check` byte-for-byte regeneration/readback is a separate guard; no registered contract requires every future consumer to run it.

This is `SAME_CLASS_DEEPER` under P40, not a request for three field-specific patches. Before any consumer relies on the packet validator as the admission boundary, either bind every owner-derived projection to the exact owner source object and type its scope, or declare exact regeneration/readback mandatory and run the sibling-field mutation falsifier at that consumer. The smallest missing source prerequisite for a replayable owner side is a registered owner artifact with a Git blob and mode binding; a positive alignment additionally requires a genuine source-qualified independent semantic basis. Missing or malformed owner data must continue to yield `not_established` or reject, never a positive default.

The minimal consumer projection is the right bounded alternative for the current provisional report: it preserves the existing direct field key while removing its unsafe unqualified value. Consolidating alignment admission into the canonical producer would be broader and needs a registered owner input, typed basis artifact, and content-bound consumer path first. There is no basis for that positive mechanism today, so this review leaves it unimplemented.

## Retained evidence

- Frozen author helper: `LOCAL/raw/q0-whole-criterion-owner-binding-author-r1-20261012/virtual_projection.py` @ SHA-256 `ee9032be198322fa51b68e59115b3d3363df68e4d4ac18516c8a7eff7e990e73`.
- Frozen patch: `LOCAL/raw/q0-whole-criterion-owner-binding-author-r1-20261012/virtual-projection.patch` @ SHA-256 `4b56eb6313d2fedd9b057bb502f0d75dab1987b63e0a9996d0998c6edda10dd4`.
- Preimage declaration: `LOCAL/raw/q0-whole-criterion-owner-binding-author-r1-20261012/preimage-declaration.json` @ SHA-256 `c9006bf7c514c808cd4f56fa6a75aef8f3212b4051b33f463476ae20d665da32`.
- Author negative controls: `LOCAL/raw/q0-whole-criterion-owner-binding-author-r1-20261012/checks/negative-controls.json` @ SHA-256 `cd358046012ffccbadd205c7ff29481b4911d4b889b93c28adacdf66a3d1d1d2`.
- Independent check stdout/stderr and direct mutation results are under `LOCAL/raw/q0-whole-criterion-owner-binding-independent-r1-20261012/`; mutation result SHA-256 `d60fb15f1a4d18031b230dd0171bca4e013ad87b11deeff46554cf5428290a99`.

No product source, index, or history was changed.
