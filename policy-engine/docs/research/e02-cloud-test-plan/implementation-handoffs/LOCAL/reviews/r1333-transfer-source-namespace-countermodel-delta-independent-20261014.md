# R1333 — R1330 source-namespace countermodel delta review

**Verdict: GO for root composition and focused runtime verification of the cumulative candidate.** R1330 corrects the R1323 test-oracle contradiction with a separate, empty registry containing exactly one fiscal source. The wrong-source query targets energy while asking for a labor source; the source and labor namespace assertions now precede the query. Product code and the R1316 source/eligibility/quota implementation are byte-identical to the previously reviewed candidate. This is a static packet/test-oracle GO, not a runtime pass or closure.

## Binding and replay

- Worktree/branch: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`, `codex/e02-unified-local-20261009`.
- Base HEAD `a02f4f8920c60e02e745ba91bbed9ab9524fcbe7`, tree `da829953b1c170f3bc69420059dc7d1af4fb06f7`; source frame `LOCAL/root-author-source-frame-r1306-r2-20261014.json@cf7bbc6d742ace36a33cb1077dbbeb2effc377da7ef723e3d7bf8d2864dc9d92`.
- R1330 cumulative patch: `LOCAL/raw/r1330-transfer-source-namespace-countermodel-successor-20261014/candidate-r1330.patch@8830908125f3a1eff9cc201396d1241ca67bb7d413f29dc397cf1bfc056f4a2e`.
- Manifest: `.../manifest-r1330.json@04ed9e36c99a0b0e1007897a357624aceadf3ddc24fa885400852d480a9f5ea8`; decision: `.../decision-r1330.md@eaa1a6c0f96983e8c643e7cd113f298acb42b92cf7d8c7089cb50741a8ed5508`.
- The packet binds the exact R1316 predecessor patch `candidate-r1316.patch@564e8e652411723ade8dd9eaf482a3f895742884151a9fb4ccc4c1f11ac4c629` and manifest `manifest-r1316.json@2a775e7ff19779e9140827e82d5c071273ce27e28c9a85e322a75675ea4a3de6`. Its R1323 predecessor BLOCK and append-only source-frame correction are bound by the manifest; I verified their cited hashes.
- `git apply --check --verbose` checked all 16 cumulative paths successfully. An independent in-memory replay matched the 16 current physical and HEAD preimages and all 16 R1330 postimage hashes and byte counts. The 15 Python postimages pass `ast.parse`. Comparison with the R1316 manifest shows 15/16 postimages unchanged; the sole delta is `policy-engine/tests/unit/scientist/search/test_lesson_transfer.py`. No product source, tests on disk, index, or Git history were written.
- The author’s runtime pytest, Ruff, native, and installed-consumer checks remain **UNRUN**; root composition and focused runtime verification are still required.

## Countermodel review

R1323 correctly found that R1316’s original negative query was run after the same test had persisted a fiscal-to-labor transfer. That labor card matched the subsequent `domain="labor"` source predicate, so expecting no result was contradictory.

R1330 changes only that test module and leaves the earlier fiscal-to-labor transfer, fresh persisted labor readback, and later quota assertions intact. The corrected negative creates `source_only = _registry(tmp_path / "source-only")`, records one fiscal card, asserts its source snapshot contains exactly one fiscal entry, and asserts the labor target namespace is empty before querying `domain="labor"` with target domain energy (virtual test lines 1560–1585). `_registry` gives this fixture a new CAS and registry root, and the function makes exactly one `record_local` call there; no prior labor record can leak from the main positive fixture.

This is discriminating against the actual source property: all other source selectors match the fiscal card, the same-tenant cross-domain path is eligible, and the target domain is different. With the candidate’s source-domain predicate, the fiscal entry is excluded before projection and the negative returns empty. If that predicate is removed, the fiscal card is admitted and can be projected to energy, so the same assertion detects the defect. Separately, the main fixture proves that a persisted labor record is returned by a fresh local `domain="labor"` read while retaining `origin_domain="fiscal"`.

The test therefore repairs the R1323 P38 problem without weakening the source filter or pretending that a persisted target card was absent. It also resolves the previous P40 same-class test-setup finding at the whole source-namespace boundary, rather than adding a field-specific product branch. No G domain-axis choice or external tenant/issuer authority is claimed; those remain `not_established`. `closure_ids=[]`.
