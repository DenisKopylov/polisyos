# Release Inputs (`release/`)

`release/**` is the committed source home for release inputs, evidence
templates, durable release ledgers, and release evidence that the release owner
has intentionally promoted for review.

Generated release output does not live here by default. Release-candidate SBOMs,
rendered notes, local bundles, and staging byproducts belong under ignored
`_build/release/**` until they are promoted to committed evidence. No release
source file may live under `_build/**`.

Use `ops/release/**` for release policy baselines and promotion gates. Use
`release-fragments/unreleased/**` for unreleased release-note input.
