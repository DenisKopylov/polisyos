# Canonical delta after encoder request-state normalization

**Disposition:** one derived dynamic-import address changed; I regenerated only `architecture/imports/dynamic.toml` with the existing `decomposition_preflight` collector/renderer and `atomic_write_text`. The registry now matches all current collector rows. Its owner, review date, expiry, and exception-policy metadata are unchanged. Public-surface artifacts and W12 were already exact, so I did not rewrite them. The deep-import baseline remains unchanged and the remaining collector delta is still open.

## Source and dynamic-import evidence

Candidate HEAD is `7574c864a605c50efc033b966807790cbd8d1781`. The changed source file `src/polisyos/data_forge/kernel/embeddings.py` has SHA-256 `3321c8511f3f206a98245fd7c02a679bc401f0f1753e3a11e91c3c1acd29d72e`. The tracked source ledger covers the two modified paths under `src/polisyos` (embeddings and its kernel README), with before/after hashes in `LOCAL/raw/canonical-encoder-delta-20261010/source-wip-current.sha-ledger.json`, SHA-256 `bc579ea4ec19fa35bfad3233aec5353f3bbe5d5ab97fa409ff50e12a82a06e6d`.

The collector selected 3,201 Python files across `src`, `tools`, `apps`, and `packages`. Its compact complete-input manifest digest is `d6ea43a576c8ee2c351c6fd8d0e89d17a62cd14fecf29eb192981e61bf9094e9` (488,697 bytes); the retained manifest file SHA-256 is `84378c4d53d0ee13b0be37648ce8c0f9c78a953e7405d52a44b90557a001ffdc`.

The only row difference before regeneration was the same `__import__("torch")` in that file moving from line 755 / ID `dynamic-9f97f1d8cc1e` to line 891 / ID `dynamic-64c1f74b1dea`. No row was added or removed semantically, and all other row fields and records were equal. Before SHA-256 was `bffc6db78f3ca9c298a28f40a2b5fa86fa276e3341828769f8047d76e55bced1`; after SHA-256 is `4f45f4d1fe215969b8c266582fe7679831438663e64656a760231597865a74df` (110,541 bytes; 249 rows). The complete rendered TOML matches the tracked artifact after regeneration. Review metadata remains `team-architecture`, `2026-05-06`, expiry `2026-08-04`; no expiry or waiver change was made.

The post-regeneration complete collector comparison exited 0, with all 249 rows and exact metadata matching. `validate_dynamic_imports()` also exited 0 with `findings=0`. Full streams and exact command metadata are retained under `LOCAL/raw/canonical-encoder-delta-20261010/`; the deciding post-regeneration stdout is `post-regen-compare-final.stdout`, SHA-256 `d6040e2459f3a8e0813b1df32988b07b3521db602dfef03705889ff6d9501af1`; the dynamic-validator stdout is 11 bytes, SHA-256 `ee1f66fdefa5a4e5790838626fb31b8b04ba700864702941f4d3f36525d369e0`.

## Public outputs and W12

The full renderer comparison found all public artifacts byte-equal before and after the dynamic-only update:

| Artifact | SHA-256 | Bytes |
| --- | --- | ---: |
| `architecture/public_surface/inventory.json` | `9e4bdbf3772894f335512c2afd7f27cc03e206475790c0338a74feedabc3b924` | 299,620 |
| `docs/reference/public-surface.md` | `c6dd74692dbd798b5bd44d21f81e5af71c81edeb220d03f07430785dad00422f` | 129,921 |
| `docs/reference/generated-artifacts.md` | `162017153eca788c1afd12bde252f3b2a6862dbdce435c233ba3099af653292e` | 267,133 |

The W12 builder object equals `architecture/policy_design_case/wave6_local_validation_ladder_manifest.json` (14,802 bytes, SHA-256 `8380214707d01c86fd46fc166be1aaecb8103cf55f456a91d9ddf0a396b80e9f`; builder-object SHA-256 `b5e904e13f34cac2033b76d1f9a803df62cbeb0e91d9727cdcfd21344e7765fa`). No public or W12 artifact was regenerated.

## Deep-import residual

A complete `tools.devx.architecture.guardrails._iter_py_files()` pass covered 2,748 Python files (compact source-manifest SHA-256 `03f05607e8cba47c96d754fa5aa90b20c8fd28c9be243d1ae6d66a6f651b6c8a`, 419,156 bytes). It found 3,716 current edges against the 3,330-edge baseline: **475 additions, 89 removals, zero same-key metadata changes**. The additions by target root are core 272, IR 106, foundry 29, data_forge 26, common 18, scientist 13, fabric 7, scholar 2, BERL 1, and Lex 1. The 89 removals are not claimed as closures.

The current baseline remains SHA-256 `da9b5c9bdaccc4efcdabcd3512f451850e072f24a381d31ad18b16376e8543a7`; the rendered collector baseline would be SHA-256 `beb1bce02e273c1943d24f236e457c07521ac2a2f48688efcb3d49e15f43224e`. I did not accept or rewrite it. The exact current delta is retained at `LOCAL/raw/canonical-encoder-delta-20261010/deep-import-current-delta.json`, SHA-256 `602f2a14941a083085ef4fb0a09aecf4e556167985463717d50465d10e6805df`; complete collector stdout is `deep-delta.stdout`, SHA-256 `c0f9dd7062e6907eb7a84cea333a7e65fa34446134035621ebc1280d99c93e0b`.

P40 is SAME_CLASS_DEEPER for the remaining deep-import boundary: the derived-address refresh does not change that decision or make the residual green. No full/native wave or semantic test suite was run; the only post-write validation was the lightweight dynamic-import checker and canonical readback.
