# LA-032 V8 independent review — 2026-10-11

## Verdict

**Bounded GO for the local layout-member reader change; LA-032 remains held/open.** V8 closes the V7 dangling-entry escape by using one shared member classifier over all six known path entries before any of the four public reader routes select or read a layout. Independent tests through the public `read_api.ukraine` facade confirm that dangling links are refused, readable file symlinks still work, and only genuine donor absence receives `{}`. I found no material defect in the reviewed local file-entry behavior.

This does not prove the original source-inventory criterion, producer provenance, custody, or currentness; it does not constitute public-surface approval or G adjudication. `closure_ids: []`.

**P40 bucket:** SAME_CLASS_DEEPER, widened to the quantity the property needs. V7's second escape was still the same absent-versus-present-invalid member class, exposed by a dangling optional donor link. V8 centralizes classification for all six known targets/priors/donor entries in both layouts and applies it before each public route. The behavioral tests and independent facade probe cover the full current set, so this review does not leave a donor-only repair ladder.

## Exact candidate and source readback

- Candidate patch: `LOCAL/raw/la032-demography-layout-reader-v8-20261011/candidate-v8-cumulative-from-cd565.patch`, SHA-256 `8681ef028c510a0215e423ac8e15aaf8dc1dfa306bb557a08245a5c4873486c3`.
- Candidate manifest: `LOCAL/raw/la032-demography-layout-reader-v8-20261011/manifest-v8.json`, SHA-256 `c9174d0a438c92172f9c23b74e759fc0eabe2b54c1f2a0c6b95a3206976dacc4`.
- Slice base: commit `cd5651c3a6897f12d32212e3521e73bb570f137b`, tree `bb7186c24000b54fdb0ab8ce8d16b55c3658995c`.
- At the initial task handoff, the attached branch was at `ac7de3f2e445afd7300116072f580319c5c0d519`. Before this note, the parent appended an ordinary commit; current readback is branch `codex/e02-unified-local-20261009`, HEAD `afce1c9497cf0d5a9b771a2e7e8e9ad7a7e972ee`, tree `3c0d71702ff14e3cb56dcad906156cc16b3dbf72`, parent `ac7de3f2e445afd7300116072f580319c5c0d519`. The candidate paths remain unchanged from the slice base. Exact current readback: `LOCAL/raw/la032-demography-layout-reader-v8-independent-review-20261011/current-preimage-check.txt`, SHA-256 `b1891ad04e1c1ca41fc57d7cee847948cd82f3543fe32f37c25cd58d381dfc05`.
- The patch remains virtual and was not applied. Independent `git apply --check --verbose` passed all four paths; full output is `LOCAL/raw/la032-demography-layout-reader-v8-independent-review-20261011/apply-check.txt`, SHA-256 `0177be0a9e7f3304d8cbeff12b75443296b7b7690a66349516adda3e0226a8d6`.

Complete four-path candidate footprint (base SHA → candidate SHA):

- `policy-engine/src/polisyos/data_forge/domains/ukraine/demography/__init__.py`: `10808586416a8060b5054a0c47a68a7e0cb5a5a3b8b4aea0776185a9cc54bdcb` → `614f06d8c1b32a84e09380e23845c5046db5842c5b0e8f8ec7f88c5d39006fbb`.
- `policy-engine/tests/unit/remediation/test_udf_05.py`: `b978bc1a3129d5502cad534a2eb29f96d0572cf7e79d2d51f7f2b3336f648ae7` → `62be0ee471b5b291c615abd12ab6a3077cb4b82a1cdc98b07208bcb0e8f2376f`.
- `policy-engine/src/polisyos/data_forge/domains/ukraine/demography/README.md`: `77cedf9c4b6aa70e680f4ec068e86f6a73e0eb661b846d8e29603c07697f99a2` → `6803c398611a4c1dfc888846db62b6f1f1b3611618485fccb57fd17f823de320`.
- New `policy-engine/release-fragments/unreleased/2026-10-11-e02-la032-demography-layout-reader.toml`: absent at base → `fafccf361e7fee31c39e57a41851299900fd04298cf37813f15821b9fff90ec3`.

## Property review and deciding evidence

The property is that an optional member is absent only when no filesystem entry exists; a supplied malformed or unreadable entry must not become a default. V8 uses `lstat` to separate absent, readable regular-file (including a resolvable symlink), and invalid entries, and checks every known member before selection. The existing isolated single-member scalar compatibility path remains limited to a genuine lone file without an explicit layout. Explicit selection still requires targets and priors, and malformed JSON or mixed/ambiguous layouts do not silently fall back.

Independent composed replay used the candidate runtime overlay with the unchanged Ukraine artifact consumer test:

```text
cwd=/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine
env=PYTHONDONTWRITEBYTECODE=1; OPENBLAS_NUM_THREADS=1; OMP_NUM_THREADS=1; MKL_NUM_THREADS=1; NUMEXPR_NUM_THREADS=1; PYTHONPATH=/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/la032-demography-layout-reader-v8-20261011/runtime-overlay:/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/src
/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/bin/python -B -m pytest -o addopts= -q -ra -vv --import-mode=importlib --maxfail=1 --basetemp /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/la032-demography-layout-reader-v8-independent-review-20261011/fixtures --junitxml /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/la032-demography-layout-reader-v8-independent-review-20261011/junit.xml /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/la032-demography-layout-reader-v8-20261011/overlay/policy-engine/tests/unit/remediation/test_udf_05.py /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/tests/unit/data_forge/domains/ukraine/test_demography_artifacts.py
```

Result: **53 passed in 0.64s**. Complete output: `LOCAL/raw/la032-demography-layout-reader-v8-independent-review-20261011/pytest-v8-indie.txt`, SHA-256 `256b4ccec83038d1a40886dd3de5e81ff74a118e80ae8fab6e1a052e5c554a96`; JUnit: `.../junit.xml`, SHA-256 `0c1200b675ce571d8a1e6701293eb42b0a891929c37b0fdfc14f3ddf5bc11567`. The fixture set is temporary and synthetic; the tests did not read production data.

I also exercised the exact public facade with an independent matrix: both layouts × each of the six member positions × all three scalar readers plus aggregate reader × omitted/selected layout. All **48** dangling-link cases refused. All **24** readable-symlink cases returned the expected payload. **10** true-absence donor cases returned the documented empty result, with explicit empty-root selection refusing. The output records the physical `read_api.ukraine` facade origin and the candidate overlay module origin: `LOCAL/raw/la032-demography-layout-reader-v8-independent-review-20261011/public_api_member_probe_v2.stdout.txt`, SHA-256 `c417ff0fb4d7e69b64de828ae381ddf22ac31cc00fcad60acdf9882fe318065e`; probe script: `.../public_api_member_probe_v2.py`.

Canonical Ruff check and format-check passed on both candidate Python postimages with the workspace root configuration and repository-relative stdin filenames. Full output, including each command and exit status: `LOCAL/raw/la032-demography-layout-reader-v8-independent-review-20261011/ruff-canonical-v8-correct-filenames.txt`, SHA-256 `6aea54bb808946eb1661ee7c85244f9c09bdf55c07732012bb06478505326714`. The V8 author receipt also retains the expected-red replay against V7: `LOCAL/raw/la032-demography-layout-reader-v8-20261011/red-v7-donor-exposed/stdout.txt`, SHA-256 `3e05a6daa03217fdaf2edc95febac042dcf974911cf955db072489221bfd4c3c`; that is author evidence, not an independent replay by this reviewer.

## Limits and next checks

The canonical criterion is LA-032 (`coverage.json` occurrence `#/findings/256`, `LA_r09` lines 1668–1715; source SHA-256 `5f5c7a56a652a0328e25fd8b6091a2f780750d9eaee8f10c0129b2f9f0609cf2`). It requires the actual source-qualified persisted inventory and the same selected state/member mapping to be consumed through the composite and sibling paths. V8 only repairs local filesystem member classification and layout selection. The original producer, persisted artifact, source-to-state mapping, custody/profile/currentness, and downstream static-aging inventory bridge remain `not_established`; the manifest lists `producer_missing`, `artifact_missing`, `bridge_missing`, `verification_missing`, and `semantic_test_missing` for that source-level claim. Next check is to obtain the genuine producer output and its content-bound, source-qualified ordered member refs, then replay all four readers and the downstream consumer against that same inventory.

The release fragment explicitly leaves `public_surface_inventory_reviewed = false`. The new scalar `layout` keyword parameters therefore remain pending public-surface inventory review/regeneration and release publication. This review does not approve or adjudicate that public API change. No formal G closure is proposed; `closure_ids: []`.
