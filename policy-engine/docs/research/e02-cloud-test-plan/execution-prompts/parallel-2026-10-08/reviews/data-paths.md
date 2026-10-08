# ORCH02 lease delta readback

Read-only verification of the updated `parallel-2026-10-08` dispatch/prompts at analysis `fe5ccf9ce90c336fff749da48bd0138d321baf23`, against exact source ranges and G `6f3983466f1eca14b510c4f5006fab5092d418d3`. No tracked file, source, ref, checkout, or test was changed/run.

## Confirmed updates

- **C05 / I1:** dispatch now leases `data_forge/kernel/pipeline/manifests.py` and `fabric/retrieval/service.py`; the DFI range contains `tests/unit/remediation/test_dfi_03.py`, and C05 names it the sole I1 defining-test writer for same-ID byte invalidation / mtime-only reuse. CAT range contains the two newly leased source files and `test_dfk_02.py`. Prompt preserves DFK-02 semantics with C-W06, assigns C05 physical ownership of that CAT companion test, and C06 review. C06 has a separate `test_dfk_01.py`; no same-path test writer remains.
- **C06 / Q2:** dispatch scopes now include the exact CAN delta sources `ir/artifacts/io.py` and `ir/artifacts/README.md`. Source pin e3cb `e3cb3fafc847b94a5d4b3adc03b814b4c711920c` is a non-G mapping delta (tree `2d27c9c1…`), with a release fragment and `test_ir_adapter.py`; the earlier adapter implementation 8f `8f13193b79b366fe26101af37427da5f44ef490a` (tree `8a26ff84…`) is already in G and remains excluded from re-import. Prompt names C06 as sole physical writer of `test_ir_adapter.py` and `test_storage_protocol_boundaries.py`, with C02 supplying Core requirements. C02's broad Core scope excludes exactly `core/artifacts/ir_adapter.py`.
- **C12 / I4:Legal:** exact `test_emb_03.py` is now the role test selector and sole writer; `lex/knowledge/README.md` is in scope. The Legal source range contains that test, the README, two shared reference pages, and one unique release fragment. Prompt sends shared references to G and gives the Legal fragment to its original owner.
- **C04 / R2:** prompt explicitly assigns `pyproject.toml` and `uv.lock` to G, and unique release fragments to the original B/C leaf owners. The stream range has two distinct C release filenames; the NET delta is the single test-only `tests/unit/fabric/data_plane/test_net_ing_registry_cleanup.py` path.
- **C06 / I2 companions:** DFK range's release fragment and plan/decision docs have original-owner slice treatment; shared references route to G. Retired deleted code paths stay read-only and are not recreated.

## Path and dependency check

Exact range membership matches the new code/test scopes: DFI `test_dfi_03.py`; CAT `manifests.py`, `retrieval/service.py`, `test_dfk_02.py`; CAN e3cb `ir/artifacts/io.py`, README and `test_ir_adapter.py`; Legal `test_emb_03.py` and `lex/knowledge/README.md`. The sidecar paths are distinct: DFK, CAN, Legal, and C stream release fragments all have different filenames; `pyproject.toml`/`uv.lock` have the single G owner. Shared Lex reference docs have the single G owner.

The all-role source-prefix check found no new collision. Existing broad overlaps are explicitly resolved: C02's `core/artifacts/` scope excludes C06's exact adapter path; C01's engine scope excludes C03's budget files. C01/C03 test selectors overlap by directory, but selectors are discovery/check inputs rather than write leases. C04/C05/C06/C12 source and named test paths are mutually disjoint.

The dependency chain remains correct: I1 and I2 start independently; I1 admits Catalog then Legal, while Legal fixtures can start early; R2 waits for Q1+R1 and I3 waits for R2 plus source facts; C06 CAN installed-reader Q2 waits for Q1. ORCH02's exact branch/path admission and COMMON's “selector is not a lease” rule remain in force. Before any mutation, carry the above unique release/doc companion assignments into the exact per-lane lease manifest; no competing filename assignment appears in this delta.
