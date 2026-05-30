# Universal Corpus Fixtures

Last updated: 2026-05-24

This directory is the W11.D machine-loadable fixture surface for the universal
Policy Design Case corpus. `manifest.json` declares public, hidden, and rotating
splits; files under `cases/` carry per-case intent, expected facets, obligation
graph slices, claim families, RequirementSpec slices, adapter bindings,
authority-level closeout states, and projection truthfulness expectations.
The case files are generated from the repo-owned W11.A/B annotations under
`docs/research/universal-policy-design/outcome-corpus/`.

Fixtures are semantic evaluation expectations. They do not satisfy runtime
evidence, legal authority, method validity, participation legitimacy, projection
authority, or closeout by themselves.
