# Canonical regeneration after facade wiring

**Disposition:** no generated artifact required regeneration. At `d12ae0a32d09d2ec7303008c7f853ef93de72aab`, the full current collectors/renderers reproduce the tracked dynamic-import inventory and all three public-surface outputs byte-for-byte after the 50-source facade-wiring slice. The W12 builder also reproduces the existing manifest. I left canonical artifacts and baselines unchanged.

## Complete inputs and retained deciding output

The dynamic-import collector selected all 3,201 `*.py` paths from `src`, `tools`, `apps`, and `packages`. Its complete input-manifest canonical digest is `d088f116ea3f05f68ccf86f4674af0d7e539757a5e7c7c458e76d523e967eb14` (488,697 canonical bytes). The pretty manifest is `LOCAL/raw/canonical-facade-wire-regen-20261010/dynamic-input-manifest.json` (file SHA-256 `6be12b77e3fd86a2526efda053dc68fca709a6ef87d31c6f02ee09f98196ce93`). Current and rendered dynamic inventories each have 249 rows with identical keys and protected metadata. The 50 tracked changed source files and before/after SHA-256 values are recorded in `LOCAL/raw/canonical-facade-wire-regen-20261010/source-wip-50.sha-ledger.json`, SHA-256 `4efab84081da8212eb643b6eb407fa4635ed97b13b099f9504bb6d6f73f4d942`.

The full comparison command was:

```text
.venv/bin/python docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/canonical-facade-wire-regen-20261010/compare_final.py
```

It exited 0 with empty stderr. The complete stdout is retained at `LOCAL/raw/canonical-facade-wire-regen-20261010/preflight-compare.stdout`, 8,199 bytes, SHA-256 `1f1bca0ec25c006caa0264014c21447ad67a2bdcfa6d25a348261b10c3329149`; its exact argv, cwd, exit code, and stream hashes are in the adjacent `.command.json`.

## Canonical artifact readback

| Artifact | Current = rendered SHA-256 | Bytes |
| --- | --- | ---: |
| `architecture/imports/dynamic.toml` | `bffc6db78f3ca9c298a28f40a2b5fa86fa276e3341828769f8047d76e55bced1` | 110,541 |
| `architecture/public_surface/inventory.json` | `9e4bdbf3772894f335512c2afd7f27cc03e206475790c0338a74feedabc3b924` | 299,620 |
| `docs/reference/public-surface.md` | `c6dd74692dbd798b5bd44d21f81e5af71c81edeb220d03f07430785dad00422f` | 129,921 |
| `docs/reference/generated-artifacts.md` | `162017153eca788c1afd12bde252f3b2a6862dbdce435c233ba3099af653292e` | 267,133 |

The W12 builder object equals `architecture/policy_design_case/wave6_local_validation_ladder_manifest.json` (14,802 bytes, SHA-256 `8380214707d01c86fd46fc166be1aaecb8103cf55f456a91d9ddf0a396b80e9f`; builder object SHA-256 `b5e904e13f34cac2033b76d1f9a803df62cbeb0e91d9727cdcfd21344e7765fa`). No W12 rebuild was needed.

The dynamic inventory's existing review metadata remains unchanged, including `review_owner=team-architecture`, `reviewed_at=2026-05-06`, and `review_expires=2026-08-04`; this comparison does not renew or waive that review.

## Deep-import boundary remains open

I did not accept or rewrite `architecture/baselines/imports/deep_import.json`. A fresh full collector pass used `tools.devx.architecture.guardrails._iter_py_files()` over 2,748 Python files; the complete compact source manifest is SHA-256 `d9addf1b9f36019610713ddef38ad507e8c7cf5f785b4be390022d4a165ae6bf` (419,156 bytes). It produced 3,716 current edges against the 3,330-edge tracked baseline: **475 added, 89 removed, zero same-key metadata changes**. The 475 additions are distributed by target root as core 272, IR 106, foundry 29, data_forge 26, common 18, scientist 13, fabric 7, scholar 2, BERL 1, and Lex 1. The removed 89 remain unproven closures.

This is the same deep-import boundary class after the separately reviewed 82 exact-object facade routes: the 475 residual edges are not blanket-accepted. The baseline remains at SHA-256 `da9b5c9bdaccc4efcdabcd3512f451850e072f24a381d31ad18b16376e8543a7`; canonical expected bytes would hash to `beb1bce02e273c1943d24f236e457c07521ac2a2f48688efcb3d49e15f43224e`. The exact current delta and source manifest are retained in `LOCAL/raw/canonical-facade-wire-regen-20261010/deep-import-current-delta.json` (SHA-256 `602f2a14941a083085ef4fb0a09aecf4e556167985463717d50465d10e6805df`) and `deep-input-manifest.json` (file SHA-256 `4c6fc88f4a53bd7a2f73867fc227ee0d21aa2b7e2634b970ce458e8e69595a2d`). The full command stdout is `deep-delta.stdout` (109,703 bytes, SHA-256 `16b857c81a93255a37fb868cf8b59161906b59f4ecb430d4726a04d37ac1dcf9`); exact invocation and stream hashes are in `deep-delta.command.json`.

P40 classification is SAME_CLASS_DEEPER, not a new permission to refresh the baseline. No expiry, exception, or clock metadata was changed. Because all canonical generated comparisons were already exact, I did not run a write-mode sync or repeat the three existing generator tests; there was no regeneration delta that could warrant them. No full native wave or model work was run.
