# Independent review: public-surface coordinate v2

Verdict: **GO for this bounded v1 coordinate repair**. The cumulative patch closes the v1 review’s version/coordinate false greens, repairs the fixture-root mismatch, and preserves unrelated API and snapshot fields. This is not a finding closure or G acceptance; the historical Phase 3A gate remains UNRUN because the current collector has a separate alias-scope delta.

## Exact target and provenance

- Patch: `LOCAL/raw/public-surface-coordinate-v2-20261011/patch.diff` SHA-256 `491b7778a824668942587dcb8449fb8484453cb42649be8468c28308fd7281c3`.
- Manifest: `LOCAL/raw/public-surface-coordinate-v2-20261011/manifest.json` SHA-256 `32a224c7ffbb285cf26869878ce354f255e2b27d1fd810b42cc32c23b779d3e4`.
- Candidate base: `f6d469b181958859752016bbad0f258ccf50bb0f`, tree `80656d52d179d37952ec14091f3839200e455272`.
- The manifest’s three exact preimages matched both hashes and worktree Git blobs. A scratch-only apply reproduced all three virtual postimage hashes exactly; `git apply --check` passed. No patch was applied to the checkout.
- This is the cumulative response to the independent v1 review at `LOCAL/reviews/public-surface-coordinate-v1-independent-review-20261011.md`, SHA-256 `e9c37113960d2bf684d3889df548ccf3952d42fc753c5d2b7462dfba0fadd1cd`.

## Behavioral evidence

- The focused candidate tests passed: **14 passed, 1 deselected**. The deselected test is the full historical baseline equality check, whose result is not established by this focused review.
- The valid v1 collector fixture shifts a public definition by two lines and the actual snapshot validator remains green; a parameter change produces drift. The retained-marker controls still detect a removed object and preserve `__all__`, signatures, FQN, kind, bases, Pydantic flag, module/nested line values, and unknown v1 row shapes.
- Version controls preserve the coordinate for version 2, missing version, boolean version, string version, and float version. Invalid source-coordinate controls preserve line `0`, `-1`, `True`, string, and `None` as drift. This closes the exact false-green class reported in v1 under the same P40 bucket by widening the single classifier to the known v1 quantity: exact JSON integer version 1 plus a positive non-bool integer line.
- Marker-preserving removal control passed independently: replacing the normalizer with identity while retaining the real comparator makes the v1 line shift produce one finding.
- The temporary source fixtures now set both `REPO_ROOT` and `SRC_ROOT` to resolved temporary paths. The alias fixture and coordinate gate fixture passed through the real collector/validator, resolving the v1 `_rel()` failure without changing product path resolution.

## Static checks and boundaries

- Canonical Ruff passed both proposed Python postimages using the workspace virtualenv, `architecture/tooling/ruff/workspace_root.toml`, and `policy-engine/...` stdin filenames.
- The historical baseline remains byte-for-byte unchanged at SHA-256 `4d8b67ee939c769b8cd52b9cdae49597d040b9680304e63356b1c449b0eef589`. The proposal retains the v1 return-annotation and class-field/constructor limitations and claims no formal closure IDs.
- The full historical gate and full test file remain UNRUN. The current alias-resolution collector delta remains outside this coordinate repair and must be reconciled against the historical baseline at final source freeze.

No product source, baseline, index, or history was changed by this review. Focused checks used scratch postimages only; G retains independent code acceptance and formal adjudication.
