# R1062 — independent review of R1061 mapping and formatter delta

**Verdict: GO to root’s focused native replay only.** This is a delta review of the R1061 compatibility and formatting companion on top of R1027. It adds no production behavior. Runtime tests remain unrun here and `closure_ids=[]`.

## Exact binding

- R1061 patch: `LOCAL/raw/r1061-v7-forecast-ref-mapping-compatibility-format-companions-20261013/candidate.patch` @ `ba8e6047fe136684269b66157fe650fa3a8ac684747ce3a9df4e4aaf75b5142c`.
- R1061 manifest: adjacent `manifest.json` @ `71cb11c53273b02ae8f15166a90c5f709e2b08586c6637f1a98b2677502c81d7`.
- R1058 base composition: `LOCAL/raw/reviewed-v7-whole-forecast-ref-r1058-20261013/composition.json` @ `d8df94f06d0ef78fe54bcf6fc1357202e866dd87452297dd43c91aeebb73d3a3`; its net patch is `1c35063f30099531f838491e86c63c1076e518c448b320c4d2a9bef168cf130f`.
- Current frame: `LOCAL/root-author-source-frame-r1059-20261013.json` @ `110476638a39394b71eef6ab6701d0ef751a53c4509f8a96fe3d221ca24930f2`; HEAD `9511169e1a7f6dbd4137de824905dfbff8992a3f`, tree `d6d48c83b5a60afdead8066253bc30cd216f5913`. The current physical target files remain the R1027 source preimages. The R1058 overlay supplies the R1027 postimages that R1061 declares as its preimages; I reviewed the delta against that overlay, not against the older physical bytes.
- R1061 source pre/post: `outcome_prediction.py` `287b41deae358f694726193191027a0db3b0c767d13f1eb624c58069ebf44437` → `b6fc06a2fff4747c87786af282f1aa20ddf4b503afbc7aeafb7651c9f6638dc4`.
- R1061 test pre/post: `test_outcome_prediction.py` `1c8ef77916403cf57f30a622dc83ccb7a9cd10266dbf1a50d7fbd2a22064fa6a` → `00a2e8eaa11361e84012db4cfa52911e43f2f7759f0dc30f338eb9e5caeef30c`.

## Delta findings

The R1061 patch changes only the two R1027 paths. On the source module it applies the two formatting edits previously observed at `_prediction_authority_boundary_is_valid` and `_stable_token`; an AST comparison of the exact R1058 source overlay and R1061 source postimage is equal. There is no source-semantic change.

The test change restores the original mapping-form wrong-kind/media negatives and keeps the new Core-ref negatives. The existing `kind/media_type` parameterization is crossed with `ref_form in {mapping, core}`: both forms are checked for each invalid kind/media pair. In the mapping branch, the original three-key mapping shape is used; the Core branch passes the Core `ArtifactRef`. The independent positive tests from R1027 still cover a selected profile and a genuinely absent profile, and assert all four selected-ref fields. Thus the delta restores the removed mapping control without weakening the Core-object negative or the separate identity/non-synthesis positives.

## Independent replay and commands

I read the exact R1058 composition and overlay. Its composition hash matches the R1061 manifest’s `base_composition_sha256`; the two overlay hashes match the R1061 preimages. A read-only, in-memory unified-hunk replay of the exact R1061 patch against those overlay bytes produced both exact manifest postimage hashes. No source file was changed.

On both final virtual postimages, from `policy-engine/`, I ran product-configured Ruff using product-relative `--stdin-filename` paths:

- `.venv/bin/python -B -m ruff check --no-cache --output-format json --stdin-filename src/polisyos/runtime/quality/design_axes/outcome_prediction.py -` and the corresponding `tests/unit/runtime/quality/design_axes/test_outcome_prediction.py` command: exit 0, stdout `[]` (SHA-256 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`), stderr empty.
- `.venv/bin/python -B -m ruff format --check --no-cache --stdin-filename <same product-relative path> -`: both exit 0 with empty stdout/stderr.

Two reviewer harness errors are retained for provenance: (1) an initial in-memory replay script used a suffix test that classified `test_outcome_prediction.py` as the source module; its expected test-AST-equality assertion failed after both image hashes had already matched. (2) the next Ruff attempt passed repository-root `policy-engine/tests/...` as `--stdin-filename` while running from `policy-engine/`, so configured per-file test ignores did not match and Ruff reported S101 for pytest assertions (stdout SHA-256 `7ff33cad1d41e17a123313dc771697459c31a70e9b342b2b29b7d5031add0268`). The corrected exact-path replay and product-relative Ruff commands above passed. These are review harness errors, not candidate failures.

No pytest, product import, runtime, or native replay was run. Root retains the R1024 preimage receipt as the actual POST → CAS/event → fresh GET witness; R1061 only repairs the unit coverage gap and source formatting on top of R1027.

## Classification and limits

- **P40:** same compatibility/format companion class as the R1053 delta note. This delta restores the mapping negative that R1027 had replaced while preserving the Core-object variants; it introduces no new runtime class or additional repair ladder.
- **P37/P38:** there is no new admission predicate. The mapping-vs-Core input representation and identical invalid kind/media refusal are explicitly tested in the test postimage, while runtime execution is `not_established` in this review. The existing selected-profile loader and R1027 DTO boundary remain the owners of identity/profile behavior.
- **Acceptance boundary:** GO only for the root-owned focused native replay against the composed R1027+R1061 source. This review does not turn the prior R1024 failure into a candidate pass and does not claim formal closure or authority acceptance.
