# B148 R11 release-recipe delta v2 independent review — 2026-10-11

## Decision

**GO for this two-path metadata/recipe delta only.** It repairs a malformed legacy release fragment, preserves the existing candidate’s stated additive compatibility, and records a real bounded review of the committed public-surface inventory. This is not G source acceptance, integration publication, or formal finding adjudication. `closure_ids` remains empty. The R11 source review remains a separate input; this note does not expand it.

## Exact inputs and boundary

- Review base: `cd5651c3a6897f12d32212e3521e73bb570f137b`, tree `bb7186c24000b54fdb0ab8ce8d16b55c3658995c`; parent `c19e502ddfa9dec45e5de72b380003250a2d676c`.
- R11 virtual parent patch: `.../LOCAL/raw/b148-import-report-dispositions-v4-r11-cas02-recovery-oracle-20261011/candidate.patch` @ `d2a8ef3e24cac4e0008d068b9263615b14c2b054ab2f089ca5bea07cec198f70`; its manifest is @ `82fdf25cf61fc3fb299ad96e362f2921bddb2e15df9fa6cf769bedc855fb113d`.
- Reviewed delta patch: `.../LOCAL/raw/b148-r11-release-recipe-delta-v2-20261011/candidate.patch` @ `758a3e9221128f13d79878af1ab6a61ad00aabb0c7dad36c7673917007d9ed19`; manifest @ `685975265eb33ed50b2da34110f0afd5839d9b8018d3ee22511e27841f8ebd9a`.
- The manifest binds exactly two R11 virtual postimages. The decision packet changes from `6f025a23995ae82487b6cc2d667fe90105bb6b136a86551d38cd04254b66eeba` to `bb1ff82d084d0b7c1600c43f263b3b51f18e64bd6c68b04e9135edbd4676981a`, deleting one surplus terminal blank line only. The release fragment changes from `de59307e44495f85359075f74317ddd1f73ada6de0ed852568b80d76f756225e` to `8d5f0a5045c3caa3f682c3e1006348656f97136d055b1bb8db3dc9bfb213a131`.
- No source, tests, architecture index, or Git history was modified for this review. The shared checkout was already dirty; this review is pinned to the candidate base above, not to a later shared-worktree state.

## Findings

The old release fragment had only a nested `[fragment]` table with `type = "fix"` and `summary`, while the release-fragment contract requires root-level `id`, `title`, `type`, `owner`, `summary`, and non-empty `evidence`. The candidate supplies these root fields, the release-supported type `fixed`, and the allowed structured `python-public-api` / `additive` compatibility row. The retained native validator output is a complete JSON result with `error_count: 0` and `finding_count: 0`; its SHA-256 is `4257a37508e2765609eb4f07ce62148607959188137f5e1d66a53eeb338c92e9`. The retained native renderer output SHA-256 is `64059b9ca89e65eab1dd9796e8575865403168d0da88e8bdd7957e6e927d2e1f`; it renders the compatibility, change class, supported surface, migration, API/runtime, limitations, and structured compatibility sections. These are retained author-run outputs, not a claim that this review reran the release toolchain.

The compatibility prose matches the R11 code/test delta: legacy `ImportReport` fields and meanings remain, receipt fields are additive/defaulted, and the previous JSON keys remain in the `bundle_import` projection. The R11 `_cli_replay.py` patch routes the same typed report through four branches (`export_missing`, `export_success`, `check`, `replay`); its parameterized test covers each branch in both JSON and text modes. The fragment therefore describes four JSON and four text paths without claiming a new generated-client contract. The R11 source reviewer’s separate note is `.../LOCAL/reviews/b148-import-report-dispositions-v4-r11-cas02-independent-review-20261011.md` @ `9e66ff6367fc879353ced2c07f4a8fcd3e5d1e6b7e852bbd00949c09726c0b41`.

I independently inspected the actual committed inventory and facade rather than relying on `public_surface_inventory_reviewed = true`:

- `policy-engine/architecture/public_surface/contract.toml` at the review base is SHA-256 `61b2268c6539b86182cb442f5d7132375011a3ac2cbf8913daa4953dbd4c9b0f`. Its `polisyos.core` package is `public_stable`, and `polisyos.core.artifacts` is a supported entrypoint.
- `policy-engine/architecture/public_surface/inventory.json` at the review base is SHA-256 `b396f9e32a47d4530b47906704f1096f17d3f76975ee338681207cdcc2bf5521`. It reports the artifact facade as `unresolved_exports` with `complete_verdict=false`; `ImportReport` appears only among declared export candidates. The reason identifies the parent `from __future__ import annotations` as outside the bounded parser. This is not complete runtime-export proof, and this review does not present it as such.
- The committed `src/polisyos/core/artifacts/__init__.py` at that base is SHA-256 `e22dc9dd7872ee0e3867924e5b0de839b6a6f65958624824b056fdf9277b2b67`: it explicitly imports `ImportReport` from `._transfer_ops` and lists it in `__all__`. The public-surface reference at that base (`docs/reference/public-surface.md`, SHA-256 `2ee2219bb108f929706f961c30d82bf5afbb09b45347ba73f8c29d69ac3502e6`) likewise calls `polisyos.core` `public_stable` and lists `polisyos.core.artifacts` as supported while disclosing unresolved export names.
- Thus the Boolean is warranted as a record that the inventory was reviewed. The `public_stable` classification derives from the supported-entrypoint contract and package classification plus the explicit facade binding; it does not claim that the generated inventory proves every export. If the inventory or supported-surface contract changes before freeze, this review must be repeated against that exact source.

The fragment’s evidence references all exist at the review base: five named tests, the CAS README and operations doc, the artifact facade, and the inventory. The candidate also explicitly limits its claims to local archive intake, local CAS transaction-stage intent, profile-qualified views, and configured verification; it disclaims law, signer trust, external custody, provenance truth, authority beyond existing admission, and production currentness. That boundary is accurate for this metadata proposal.

## Retained deciding artifacts

All paths below are relative to `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b148-r11-release-recipe-delta-v2-20261011/`:

- `candidate-fragment.toml` @ `8d5f0a5045c3caa3f682c3e1006348656f97136d055b1bb8db3dc9bfb213a131`.
- `release-validator.stdout.txt` @ `4257a37508e2765609eb4f07ce62148607959188137f5e1d66a53eeb338c92e9`.
- `release-render.stdout.txt` @ `64059b9ca89e65eab1dd9796e8575865403168d0da88e8bdd7957e6e927d2e1f`.
- `apply-check.stdout.txt` @ `8b8d5ebcdaf23113d7014a6103f77f9136105e2c1967dc324a2126e5e7241c38`; `diff-check.stdout.txt` @ `75ebccfc18cc5b1a8b32589edccfa2e9f53d9f4dcde857010b3235519655e37f`.

`GO` applies only to the two-path delta over exact R11 virtual postimages. The full composed source/input/profile/backend freeze and G’s independent acceptance and adjudication remain outstanding.
